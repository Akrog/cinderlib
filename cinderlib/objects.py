# Copyright (c) 2018, Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import
import json as json_lib
import uuid

from cinder import context
# NOTE(geguileo): Probably a good idea not to depend on cinder.cmd.volume
# having all the other imports as they could change.
from cinder.cmd import volume as volume_cmd
from cinder import objects as cinder_objs
from cinder import exception as cinder_exception
from cinder.objects import base as cinder_base_ovo
from os_brick import exception as brick_exception
from os_brick import initiator as brick_initiator
from os_brick.initiator import connector as brick_connector
from oslo_log import log as logging
from oslo_utils import timeutils
import six

from cinderlib import exception


LOG = logging.getLogger(__name__)
DEFAULT_PROJECT_ID = 'cinderlib'
DEFAULT_USER_ID = 'cinderlib'
BACKEND_NAME_VOLUME_FIELD = 'availability_zone'
BACKEND_NAME_SNAPSHOT_FIELD = 'progress'
CONNECTIONS_OVO_FIELD = 'volume_attachment'


# This cannot go in the setup method because cinderlib objects need them to
# be setup to set OVO_CLASS
volume_cmd.objects.register_all()


class KeyValue(object):
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value

    def __eq__(self, other):
        return (self.key, self.value) == (other.key, other.value)


class Object(object):
    """Base class for our resource representation objects."""
    DEFAULT_FIELDS_VALUES = {}
    LAZY_PROPERTIES = tuple()
    backend_class = None
    CONTEXT = context.RequestContext(user_id=DEFAULT_USER_ID,
                                     project_id=DEFAULT_PROJECT_ID,
                                     is_admin=True,
                                     overwrite=False)

    def _get_backend(self, backend_name_or_obj):
        if isinstance(backend_name_or_obj, six.string_types):
            try:
                return self.backend_class.backends[backend_name_or_obj]
            except KeyError:
                if self.backend_class.fail_on_missing_backend:
                    raise
        return backend_name_or_obj

    def __init__(self, backend, **fields_data):
        self.backend = self._get_backend(backend)
        __ovo = fields_data.get('__ovo')
        if __ovo:
            self._ovo = __ovo
        else:
            self._ovo = self._create_ovo(**fields_data)

        # Store a reference to the cinderlib obj in the OVO for serialization
        self._ovo._cl_obj_ = self

    @classmethod
    def setup(cls, persistence_driver, backend_class, project_id, user_id,
              non_uuid_ids):
        cls.persistence = persistence_driver
        cls.backend_class = backend_class

        # Set the global context if we aren't using the default
        project_id = project_id or DEFAULT_PROJECT_ID
        user_id = user_id or DEFAULT_USER_ID

        if (project_id != cls.CONTEXT.project_id or
                user_id != cls.CONTEXT.user_id):

            cls.CONTEXT.user_id = user_id
            cls.CONTEXT.project_id = project_id
            Volume.DEFAULT_FIELDS_VALUES['user_id'] = user_id
            Volume.DEFAULT_FIELDS_VALUES['project_id'] = project_id

        # Configure OVOs to support non_uuid_ids
        if non_uuid_ids:
            for ovo_name in cinder_base_ovo.CinderObjectRegistry.obj_classes():
                ovo_cls = getattr(volume_cmd.objects, ovo_name)
                if 'id' in ovo_cls.fields:
                    ovo_cls.fields['id'] = cinder_base_ovo.fields.StringField()

    def _to_primitive(self):
        """Return custom cinderlib data for serialization."""
        return None

    def _create_ovo(self, **fields_data):
        # The base are the default values we define on our own classes
        fields_values = self.DEFAULT_FIELDS_VALUES.copy()

        # Apply the values defined by the caller
        fields_values.update(fields_data)

        # We support manually setting the id, so set only if not already set
        # or if set to None
        if not fields_values.get('id'):
            fields_values['id'] = self.new_uuid()

        # Set non set field values based on OVO's default value and on whether
        # it is nullable or not.
        for field_name, field in self.OVO_CLASS.fields.items():
            if field.default != cinder_base_ovo.fields.UnspecifiedDefault:
                fields_values.setdefault(field_name, field.default)
            elif field.nullable:
                fields_values.setdefault(field_name, None)

        if ('created_at' in self.OVO_CLASS.fields and
                not fields_values.get('created_at')):
            fields_values['created_at'] = timeutils.utcnow()
        return self.OVO_CLASS(context=self.CONTEXT, **fields_values)

    @property
    def json(self):
        ovo = self._ovo.obj_to_primitive()
        return {'class': type(self).__name__,
                'backend': getattr(self.backend, 'config', self.backend),
                'ovo': ovo}

    @property
    def jsons(self):
        return json_lib.dumps(self.json, separators=(',', ':'))

    def _only_ovo_data(self, ovo):
        if isinstance(ovo, dict):
            if 'versioned_object.data' in ovo:
                value = ovo['versioned_object.data']
                if ['objects'] == value.keys():
                    return self._only_ovo_data(value['objects'])
                key = ovo['versioned_object.name'].lower()
                return {key: self._only_ovo_data(value)}

            for key in ovo.keys():
                ovo[key] = self._only_ovo_data(ovo[key])
        if isinstance(ovo, list) and ovo:
            return [self._only_ovo_data(e) for e in ovo]
        return ovo

    def to_dict(self):
        json_ovo = self.json
        return self._only_ovo_data(json_ovo['ovo'])

    @property
    def dump(self):
        # Make sure we load lazy loading properties
        for lazy_property in self.LAZY_PROPERTIES:
            getattr(self, lazy_property)
        return self.json

    @property
    def dumps(self):
        return json_lib.dumps(self.dump, separators=(',', ':'))

    def __repr__(self):
        backend = self.backend
        if isinstance(self.backend, self.backend_class):
            backend = backend.id
        return ('<cinderlib.%s object %s on backend %s>' %
                (type(self).__name__, self.id, backend))

    @classmethod
    def load(cls, json_src, save=False):
        backend = cls.backend_class.load_backend(json_src['backend'])
        ovo = cinder_base_ovo.CinderObject.obj_from_primitive(json_src['ovo'],
                                                              cls.CONTEXT)
        return cls._load(backend, ovo, save=save)

    @staticmethod
    def new_uuid():
        return str(uuid.uuid4())

    def __getattr__(self, name):
        if name == '_ovo':
            raise AttributeError('Attribute _ovo is not yet set')
        return getattr(self._ovo, name)


class NamedObject(Object):
    def __init__(self, backend, **fields_data):
        if 'description' in fields_data:
            fields_data['display_description'] = fields_data.pop('description')
        if 'name' in fields_data:
            fields_data['display_name'] = fields_data.pop('name')
        super(NamedObject, self).__init__(backend, **fields_data)

    @property
    def name(self):
        return self._ovo.display_name

    @property
    def description(self):
        return self._ovo.display_description

    @property
    def name_in_storage(self):
        return self._ovo.name


class LazyVolumeAttr(object):
    LAZY_PROPERTIES = ('volume',)

    def __init__(self, volume):
        if volume:
            self._volume = volume
            # Ensure circular reference is set
            self._ovo.volume = volume._ovo
            self._ovo.volume_id = volume._ovo.id
        elif self._ovo.obj_attr_is_set('volume'):
            self._volume = Volume._load(self.backend, self._ovo.volume)

    @property
    def volume(self):
        # Lazy loading
        if self._volume is None:
            self._volume = Volume.get_by_id(self.volume_id)
            self._ovo.volume = self._volume._ovo
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._ovo.volume = value._ovo

    def refresh(self):
        last_self = self.get_by_id(self.id)
        if self._volume is not None:
            last_self.volume
        vars(self).clear()
        vars(self).update(vars(last_self))


class Volume(NamedObject):
    OVO_CLASS = volume_cmd.objects.Volume
    DEFAULT_FIELDS_VALUES = {
        'size': 1,
        'user_id': Object.CONTEXT.user_id,
        'project_id': Object.CONTEXT.project_id,
        'host': volume_cmd.CONF.host,
        'status': 'creating',
        'attach_status': 'detached',
        'metadata': {},
        'admin_metadata': {},
        'glance_metadata': {},
    }
    LAZY_PROPERTIES = ('snapshots', 'connections')

    _ignore_keys = ('id', CONNECTIONS_OVO_FIELD, 'snapshots')

    def __init__(self, backend_or_vol, **kwargs):
        # Accept backend name for convenience
        if isinstance(backend_or_vol, six.string_types):
            kwargs.setdefault(BACKEND_NAME_VOLUME_FIELD, backend_or_vol)
            backend_or_vol = self._get_backend(backend_or_vol)
        elif isinstance(backend_or_vol, self.backend_class):
            kwargs.setdefault(BACKEND_NAME_VOLUME_FIELD, backend_or_vol.id)
        # Accept a volume as additional source data
        elif isinstance(backend_or_vol, Volume):
            # Availability zone (backend) will be the same as the source
            kwargs.pop(BACKEND_NAME_VOLUME_FIELD, None)
            for key in backend_or_vol._ovo.fields:
                if (backend_or_vol._ovo.obj_attr_is_set(key) and
                        key not in self._ignore_keys):
                    kwargs.setdefault(key, getattr(backend_or_vol._ovo, key))
            backend_or_vol = backend_or_vol.backend

        if '__ovo' not in kwargs:
            kwargs[CONNECTIONS_OVO_FIELD] = (
                volume_cmd.objects.VolumeAttachmentList(context=self.CONTEXT))
            kwargs['snapshots'] = (
                volume_cmd.objects.SnapshotList(context=self.CONTEXT))
            self._snapshots = []
            self._connections = []

        super(Volume, self).__init__(backend_or_vol, **kwargs)
        self._populate_data()
        self.local_attach = None

    @property
    def snapshots(self):
        # Lazy loading
        if self._snapshots is None:
            self._snapshots = self.persistence.get_snapshots(volume_id=self.id)
            for snap in self._snapshots:
                snap.volume = self

            ovos = [snap._ovo for snap in self._snapshots]
            self._ovo.snapshots = cinder_objs.SnapshotList(objects=ovos)
            self._ovo.obj_reset_changes(('snapshots',))
        return self._snapshots

    @property
    def connections(self):
        # Lazy loading
        if self._connections is None:
            self._connections = self.persistence.get_connections(
                volume_id=self.id)
            for conn in self._connections:
                conn.volume = self
            ovos = [conn._ovo for conn in self._connections]
            setattr(self._ovo, CONNECTIONS_OVO_FIELD,
                    cinder_objs.VolumeAttachmentList(objects=ovos))
            self._ovo.obj_reset_changes((CONNECTIONS_OVO_FIELD,))

        return self._connections

    @classmethod
    def get_by_id(cls, volume_id):
        result = cls.persistence.get_volumes(volume_id=volume_id)
        if not result:
            raise exception.VolumeNotFound(volume_id=volume_id)
        return result[0]

    @classmethod
    def get_by_name(cls, volume_name):
        return cls.persistence.get_volumes(volume_name=volume_name)

    def _populate_data(self):
        if self._ovo.obj_attr_is_set('snapshots'):
            self._snapshots = []
            for snap_ovo in self._ovo.snapshots:
                # Set circular reference
                snap_ovo.volume = self._ovo
                Snapshot._load(self.backend, snap_ovo, self)
        else:
            self._snapshots = None

        if self._ovo.obj_attr_is_set(CONNECTIONS_OVO_FIELD):
            self._connections = []
            for conn_ovo in getattr(self._ovo, CONNECTIONS_OVO_FIELD):
                # Set circular reference
                conn_ovo.volume = self._ovo
                Connection._load(self.backend, conn_ovo, self)
        else:
            self._connections = None

    @classmethod
    def _load(cls, backend, ovo, save=None):
        vol = cls(backend, __ovo=ovo)
        if save:
            vol.save()
            if vol._snapshots:
                for s in vol._snapshots:
                    s.obj_reset_changes()
                    s.save()
            if vol._connections:
                for c in vol._connections:
                    c.obj_reset_changes()
                    c.save()
        return vol

    def create(self):
        try:
            model_update = self.backend.driver.create_volume(self._ovo)
            self._ovo.status = 'available'
            if model_update:
                self._ovo.update(model_update)
            self.backend._volume_created(self)
        except Exception:
            self._ovo.status = 'error'
            # TODO: raise with the vol info
            raise
        finally:
            self.save()

    def delete(self):
        # Some backends delete existing snapshots while others leave them
        try:
            self.backend.driver.delete_volume(self._ovo)
            self.persistence.delete_volume(self)
            self.backend._volume_removed(self)
        except Exception:
            # We don't change status to error on deletion error, we assume it
            # just didn't complete.
            # TODO: raise with the vol info
            raise

    def extend(self, size):
        volume = self._ovo
        volume.previous_status = volume.status
        volume.status = 'extending'
        try:
            self.backend.driver.extend_volume(volume, size)
            volume.size = size
            volume.status = volume.previous_status
            volume.previous_status = None
        except Exception:
            volume.status = 'error'
            # TODO: raise with the vol info
            raise
        finally:
            self.save()

    def clone(self, **new_vol_attrs):
        new_vol_attrs['source_vol_id'] = self.id
        new_vol = Volume(self, **new_vol_attrs)
        try:
            model_update = self.backend.driver.create_cloned_volume(
                new_vol._ovo, self._ovo)
            new_vol.status = 'available'
            if model_update:
                new_vol.update(model_update)
            self.backend._volume_created(new_vol)
        except Exception:
            new_vol.status = 'error'
            # TODO: raise with the new volume info
            raise
        finally:
            new_vol.save()
        return new_vol

    def create_snapshot(self, name='', description='', **kwargs):
        snap = Snapshot(self, name=name, description=description, **kwargs)
        snap.create()
        if self._snapshots is not None:
            self._snapshots.append(snap)
            self._ovo.snapshots.objects.append(snap._ovo)
        return snap

    def attach(self):
        connector_dict = brick_connector.get_connector_properties(
            self.backend_class.root_helper,
            volume_cmd.CONF.my_ip,
            self.backend.configuration.use_multipath_for_image_xfer,
            self.backend.configuration.enforce_multipath_for_image_xfer)
        conn = self.connect(connector_dict)
        try:
            conn.attach()
        except Exception:
            self.disconnect(conn)
            raise
        return conn

    def detach(self, force=False, ignore_errors=False):
        if not self.local_attach:
            raise Exception('Not attached')
        exc = brick_exception.ExceptionChainer()

        conn = self.local_attach
        try:
            conn.detach(force, ignore_errors, exc)
        except Exception:
            if not force:
                raise

        with exc.context(force, 'Unable to disconnect'):
            conn.disconnect(force)

        if exc and not ignore_errors:
            raise exc

    def connect(self, connector_dict, **ovo_fields):
        model_update = self.backend.driver.create_export(self.CONTEXT,
                                                         self._ovo,
                                                         connector_dict)
        if model_update:
            self._ovo.update(model_update)
            self.save()

        try:
            conn = Connection.connect(self, connector_dict, **ovo_fields)
            if self._connections is not None:
                self._connections.append(conn)
                ovo_conns = getattr(self._ovo, CONNECTIONS_OVO_FIELD).objects
                ovo_conns.append(conn._ovo)
            self._ovo.status = 'in-use'
            self.save()
        except Exception:
            self._remove_export()
            # TODO: Improve raised exception
            raise
        return conn

    def _disconnect(self, connection):
        self._remove_export()
        if self._connections is not None:
            self._connections.remove(connection)
            ovo_conns = getattr(self._ovo, CONNECTIONS_OVO_FIELD).objects
            ovo_conns.remove(connection._ovo)

        if not self.connections:
            self._ovo.status = 'available'
            self.save()

    def disconnect(self, connection, force=False):
        connection._disconnect(force)
        self._disconnect(connection)

    def cleanup(self):
        for attach in self.attachments:
            attach.detach()
        self._remove_export()

    def _remove_export(self):
        self.backend.driver.remove_export(self._context, self._ovo)

    def refresh(self):
        last_self = self.get_by_id(self.id)
        if self._snapshots is not None:
            last_self.snapshots
        if self._connections is not None:
            last_self.connections
        vars(self).clear()
        vars(self).update(vars(last_self))

    def save(self):
        self.persistence.set_volume(self)


class Connection(Object, LazyVolumeAttr):
    """Cinderlib Connection info that maps to VolumeAttachment.

    On Pike we don't have the connector field on the VolumeAttachment ORM
    instance so we use the connection_info to store everything.

    We'll have a dictionary:
        {'conn': connection info
         'connector': connector dictionary
         'device': result of connect_volume}
    """
    OVO_CLASS = volume_cmd.objects.VolumeAttachment

    @classmethod
    def connect(cls, volume, connector, **kwargs):
        conn_info = volume.backend.driver.initialize_connection(
            volume._ovo, connector)
        conn = cls(volume.backend,
                   connector=connector,
                   volume=volume,
                   status='attached',
                   attach_mode='rw',
                   connection_info={'conn': conn_info},
                   **kwargs)
        conn.connector_info = connector
        conn.save()
        return conn

    @staticmethod
    def _is_multipathed_conn(kwargs):
        # Priority:
        #  - kwargs['use_multipath']
        #  - Multipath in connector_dict in kwargs or _ovo
        #  - Detect from connection_info data from OVO in kwargs

        if 'use_multipath' in kwargs:
            return kwargs['use_multipath']

        connector = kwargs.get('connector') or {}
        conn_info = kwargs.get('connection_info') or {}

        if '__ovo' in kwargs:
            ovo = kwargs['__ovo']
            conn_info = conn_info or ovo.connection_info or {}
            connector = connector or ovo.connection_info.get('connector') or {}

        if 'multipath' in connector:
            return connector['multipath']

        # If multipathed not defined autodetect based on connection info
        conn_info = conn_info['conn']['data']
        iscsi_mp = 'target_iqns' in conn_info and 'target_portals' in conn_info
        fc_mp = not isinstance(conn_info.get('target_wwn', ''),
                               six.string_types)
        return iscsi_mp or fc_mp

    def __init__(self, *args, **kwargs):
        self.use_multipath = self._is_multipathed_conn(kwargs)

        scan_attempts = brick_initiator.DEVICE_SCAN_ATTEMPTS_DEFAULT
        self.scan_attempts = kwargs.pop('device_scan_attempts', scan_attempts)
        volume = kwargs.pop('volume')
        self._connector = None

        super(Connection, self).__init__(*args, **kwargs)
        LazyVolumeAttr.__init__(self, volume)

    @property
    def conn_info(self):
        conn_info = self._ovo.connection_info
        if conn_info:
            return conn_info.get('conn')
        return {}

    @conn_info.setter
    def conn_info(self, value):
        if not value:
            self._ovo.connection_info = None
            return

        if self._ovo.connection_info is None:
            self._ovo.connection_info = {}
        self._ovo.connection_info['conn'] = value

    @property
    def protocol(self):
        return self.conn_info.get('driver_volume_type')

    @property
    def connector_info(self):
        if self.connection_info:
            return self.connection_info.get('connector')
        return None

    @connector_info.setter
    def connector_info(self, value):
        self.connection_info['connector'] = value
        # Since we are changing the dictionary the OVO won't detect the change
        self._changed_fields.add('connection_info')

    @property
    def device(self):
        if self.connection_info:
            return self.connection_info.get('device')
        return None

    @device.setter
    def device(self, value):
        if value:
            self.connection_info['device'] = value
        else:
            self.connection_info.pop('device', None)
        # Since we are changing the dictionary the OVO won't detect the change
        self._changed_fields.add('connection_info')

    @property
    def path(self):
        device = self.device
        if not device:
            return None
        return device['path']

    @property
    def connector(self):
        if not self._connector:
            if not self.conn_info:
                return None
            self._connector = brick_connector.InitiatorConnector.factory(
                self.protocol, self.backend_class.root_helper,
                use_multipath=self.use_multipath,
                device_scan_attempts=self.scan_attempts,
                # NOTE(geguileo): afaik only remotefs uses the connection info
                conn=self.conn_info,
                do_local_attach=True)
        return self._connector

    @property
    def attached(self):
        return bool(self.device)

    @property
    def connected(self):
        return bool(self.conn_info)

    @classmethod
    def _load(cls, backend, ovo, volume=None, save=False):
        # We let the __init__ method set the _volume if exists
        conn = cls(backend, __ovo=ovo, volume=volume)
        if save:
            conn.save()
        # Restore circular reference only if we have all the elements
        if conn._volume and conn._volume._connections is not None:
            conn._volume._connections.append(conn)
            ovo_conns = getattr(conn._volume._ovo,
                                CONNECTIONS_OVO_FIELD).objects
            if ovo not in ovo_conns:
                ovo_conns.append(ovo)
        return conn

    def _disconnect(self, force=False):
        self.backend.driver.terminate_connection(self.volume._ovo,
                                                 self.connector_info,
                                                 force=force)
        self.conn_info = None
        self._ovo.status = 'detached'
        self.persistence.delete_connection(self)

    def disconnect(self, force=False):
        self._disconnect(force)
        self.volume._disconnect(self)

    def device_attached(self, device):
        self.device = device
        self.save()

    def attach(self):
        device = self.connector.connect_volume(self.conn_info['data'])
        self.device_attached(device)
        try:
            unavailable = not self.connector.check_valid_device(self.path)
        except Exception:
            unavailable = True
            LOG.exception('Could not validate device %s', self.path)

        if unavailable:
            raise cinder_exception.DeviceUnavailable(
                path=self.path, attach_info=self._ovo.connection_information,
                reason=('Unable to access the backend storage via path '
                        '%s.') % self.path)
        if self._volume:
            self.volume.local_attach = self

    def detach(self, force=False, ignore_errors=False, exc=None):
        if not exc:
            exc = brick_exception.ExceptionChainer()
        with exc.context(force, 'Disconnect failed'):
            self.connector.disconnect_volume(self.conn_info['data'],
                                             self.device,
                                             force=force,
                                             ignore_errors=ignore_errors)
        if not exc or ignore_errors:
            if self._volume:
                self.volume.local_attach = None
            self.device = None
            self.save()
            self._connector = None

        if exc and not ignore_errors:
            raise exc

    @classmethod
    def get_by_id(cls, connection_id):
        result = cls.persistence.get_connections(connection_id=connection_id)
        if not result:
            msg = 'id=%s' % connection_id
            raise exception.ConnectionNotFound(filter=msg)
        return result[0]

    @property
    def backend(self):
        if self._backend is None and hasattr(self, '_volume'):
            self._backend = self.volume.backend
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value

    def save(self):
        self.persistence.set_connection(self)


class Snapshot(NamedObject, LazyVolumeAttr):
    OVO_CLASS = volume_cmd.objects.Snapshot
    DEFAULT_FIELDS_VALUES = {
        'status': 'creating',
        'metadata': {},
    }

    def __init__(self, volume, **kwargs):
        param_backend = self._get_backend(kwargs.pop('backend', None))

        if '__ovo' in kwargs:
            backend = kwargs['__ovo'][BACKEND_NAME_SNAPSHOT_FIELD]
        else:
            kwargs.setdefault('user_id', volume.user_id)
            kwargs.setdefault('project_id', volume.project_id)
            kwargs['volume_id'] = volume.id
            kwargs['volume_size'] = volume.size
            kwargs['volume_type_id'] = volume.volume_type_id
            kwargs['volume'] = volume._ovo
            if volume:
                backend = volume.backend.id
                kwargs[BACKEND_NAME_SNAPSHOT_FIELD] = backend
            else:
                backend = param_backend and param_backend.id

        if not (backend or param_backend):
            raise

        if backend and param_backend and param_backend.id != backend:
            raise

        super(Snapshot, self).__init__(backend=param_backend or backend,
                                       **kwargs)
        LazyVolumeAttr.__init__(self, volume)

    @classmethod
    def _load(cls, backend, ovo, volume=None, save=False):
        # We let the __init__ method set the _volume if exists
        snap = cls(volume, backend=backend, __ovo=ovo)
        if save:
            snap.save()
        # Restore circular reference only if we have all the elements
        if snap._volume and snap._volume._snapshots is not None:
            snap._volume._snapshots.append(snap)
            if ovo not in snap._volume._ovo.snapshots.objects:
                snap._volume._ovo.snapshots.objects.append(ovo)
        return snap

    def create(self):
        try:
            model_update = self.backend.driver.create_snapshot(self._ovo)
            self._ovo.status = 'available'
            if model_update:
                self._ovo.update(model_update)
        except Exception:
            self._ovo.status = 'error'
            # TODO: raise with the vol info
            raise
        finally:
            self.save()

    def delete(self):
        try:
            self.backend.driver.delete_snapshot(self._ovo)
            self.persistence.delete_snapshot(self)
        except Exception:
            # We don't change status to error on deletion error, we assume it
            # just didn't complete.
            # TODO: raise with the snap info
            raise
        if self._volume is not None and self._volume._snapshots is not None:
            try:
                self._volume._snapshots.remove(self)
                self._volume._ovo.snapshots.objects.remove(self._ovo)
            except ValueError:
                pass

    def create_volume(self, **new_vol_params):
        new_vol_params.setdefault('size', self.volume_size)
        new_vol_params['snapshot_id'] = self.id
        new_vol = Volume(self.volume, **new_vol_params)
        try:
            model_update = self.backend.driver.create_volume_from_snapshot(
                new_vol._ovo, self._ovo)
            new_vol._ovo.status = 'available'
            if model_update:
                new_vol._ovo.update(model_update)
            self.backend._volume_created(new_vol)
        except Exception:
            new_vol._ovo.status = 'error'
            # TODO: raise with the new volume info
            raise
        finally:
            new_vol.save()

        return new_vol

    @classmethod
    def get_by_id(cls, snapshot_id):
        result = cls.persistence.get_snapshots(snapshot_id=snapshot_id)
        if not result:
            raise exception.SnapshotNotFound(snapshot_id=snapshot_id)
        return result[0]

    @classmethod
    def get_by_name(cls, snapshot_name):
        return cls.persistence.get_snapshots(snapshot_name=snapshot_name)

    def save(self):
        self.persistence.set_snapshot(self)


setup = Object.setup
CONTEXT = Object.CONTEXT
