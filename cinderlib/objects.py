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
from cinder.objects import base as cinder_base_ovo
from cinder import utils
from os_brick import exception as brick_exception
from oslo_utils import timeutils
from oslo_versionedobjects import base as base_ovo
import six

from cinderlib import exception


DEFAULT_PROJECT_ID = 'cinderlib'
DEFAULT_USER_ID = 'cinderlib'


# This cannot go in the setup method because cinderlib objects need them to
# be setup to set OVO_CLASS
volume_cmd.objects.register_all()


class Object(object):
    """Base class for our resource representation objects."""
    DEFAULT_FIELDS_VALUES = {}
    backend_class = None
    CONTEXT = context.RequestContext(user_id=DEFAULT_USER_ID,
                                     project_id=DEFAULT_PROJECT_ID,
                                     is_admin=True,
                                     overwrite=False)

    def __init__(self, backend, **fields_data):
        if isinstance(backend, six.string_types):
            self.backend = self.backend_class.backends[backend]
        else:
            self.backend = backend

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
                'backend': self.backend.config,
                'ovo': ovo}

    @property
    def jsons(self):
        return json_lib.dumps(self.json)

    def __repr__(self):
        return ('<cinderlib.%s object %s on backend %s>' %
                (type(self).__name__,
                 self.id,
                 self.backend.id))

    @classmethod
    def load(cls, json_src):
        backend = cls.backend_class.load_backend(json_src['backend'])

        backend_name = json_src['backend']['volume_backend_name']
        if backend_name in cls.backend_class.backends:
            backend = cls.backend_class.backends[backend_name]
        elif len(json_src['backend']) == 1:
            raise Exception('Backend not present in system or json.')
        else:
            backend = cls.backend_class(**json_src['backend'])

        ovo = cinder_base_ovo.CinderObject.obj_from_primitive(json_src['ovo'],
                                                              cls.CONTEXT)
        return cls._load(backend, ovo)

    def _replace_ovo(self, ovo):
        self._ovo = ovo

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

    _ignore_keys = ('id', 'volume_attachment', 'snapshots')

    def __init__(self, backend_or_vol, **kwargs):
        # Accept backend name for convenience
        if isinstance(backend_or_vol, six.string_types):
            kwargs.setdefault('availability_zone', backend_or_vol)
            backend_or_vol = self.backend_class.backends[backend_or_vol]
        elif isinstance(backend_or_vol, self.backend_class):
            kwargs.setdefault('availability_zone', backend_or_vol.id)
        # Accept a volume as additional source data
        elif isinstance(backend_or_vol, Volume):
            # Availability zone (backend) will be the same as the source
            kwargs.pop('availability_zone', None)
            for key in backend_or_vol._ovo.fields:
                if (backend_or_vol._ovo.obj_attr_is_set(key) and
                        key not in self._ignore_keys):
                    kwargs.setdefault(key, getattr(backend_or_vol._ovo, key))
            backend_or_vol = backend_or_vol.backend

        if '__ovo' not in kwargs:
            kwargs.setdefault(
                'volume_attachment',
                volume_cmd.objects.VolumeAttachmentList(context=self.CONTEXT))
            kwargs.setdefault(
                'snapshots',
                volume_cmd.objects.SnapshotList(context=self.CONTEXT))

        super(Volume, self).__init__(backend_or_vol, **kwargs)
        self._snapshots = None
        self._connections = None
        self._populate_data()

    def _to_primitive(self):
        local_attach = self.local_attach.id if self.local_attach else None
        return {'local_attach': local_attach}

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
            self._ovo.volume_attachment = cinder_objs.VolumeAttachmentList(
                objects=ovos)
            self._ovo.obj_reset_changes(('volume_attachment',))

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

    @classmethod
    def _load(cls, backend, ovo):
        # Restore snapshot's circular reference removed on serialization
        # for snap in ovo.snapshots:
        #    snap.volume = ovo

        # If this object is already present it will be replaced
        obj = Object.objects['Volume'].get(ovo.id)
        if obj:
            obj._replace_ovo(ovo)
        else:
            obj = cls(backend, __ovo=ovo)
        return obj

    def _replace_ovo(self, ovo):
        super(Volume, self)._replace_ovo(ovo)
        self._populate_data()

    def _populate_data(self):
        # old_snapshots = {snap.id: snap for snap in self.snapshots}

        # for snap_ovo in self._ovo.snapshots:
        #     snap = Object.objects['Snapshot'].get(snap_ovo.id)
        #     if snap:
        #         snap._replace_ovo(snap_ovo)
        #         del old_snapshots[snap.id]
        #     else:
        #         snap = Snapshot(self, __ovo=snap_ovo)
        #         self.snapshots.append(snap)

        # for snap_id, snap in old_snapshots.items():
        #     self.snapshots.remove(snap)
        #     # We leave snapshots in the global DB just in case...
        #     # del Object.objects['Snapshot'][snap_id]

        # old_connections = {conn.id: conn for conn in self.connections}

        # for conn_ovo in self._ovo.volume_attachment:
        #     conn = Object.objects['Connection'].get(conn_ovo.id)
        #     if conn:
        #         conn._replace_ovo(conn_ovo)
        #         del old_connections[conn.id]
        #     else:
        #         conn = Connection(self.backend, volume=self, __ovo=conn_ovo)
        #         self.connections.append(conn)

        # for conn_id, conn in old_connections.items():
        #     self.connections.remove(conn)
        #     # We leave connections in the global DB just in case...
        #     # del Object.objects['Connection'][conn_id]

        data = getattr(self._ovo, 'cinderlib_data', {})
        self.local_attach = data.get('local_attach', None)
        if self.local_attach:
            self.local_attach = Object.objects['Connection'][self.local_attach]

    def create(self):
        try:
            model_update = self.backend.driver.create_volume(self._ovo)
            self._ovo.status = 'available'
            if model_update:
                self._ovo.update(model_update)
        except Exception:
            self._ovo.status = 'error'
            # TODO: raise with the vol info
            raise
        finally:
            self.persistence.set_volume(self)

    def delete(self):
        # Some backends delete existing snapshots while others leave them
        try:
            self.backend.driver.delete_volume(self._ovo)
            self.persistence.delete_volume(self)
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
            self.persistence.set_volume(self)

    def clone(self, **new_vol_attrs):
        new_vol_attrs['source_vol_id'] = self.id
        new_vol = Volume(self, **new_vol_attrs)
        try:
            model_update = self.backend.driver.create_cloned_volume(
                new_vol._ovo, self._ovo)
            new_vol.status = 'available'
            if model_update:
                new_vol.update(model_update)
        except Exception:
            new_vol.status = 'error'
            # TODO: raise with the new volume info
            raise
        finally:
            self.persistence.set_volume(new_vol)
        return new_vol

    def create_snapshot(self, name='', description='', **kwargs):
        snap = Snapshot(self, name=name, description=description, **kwargs)
        snap.create()
        if self._snapshots is not None:
            self._snapshots.append(snap)
            self._ovo.snapshots.objects.append(snap._ovo)
        return snap

    def attach(self):
        connector_dict = utils.brick_get_connector_properties(
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
            self.persistence.set_volume(self)

        try:
            conn = Connection.connect(self, connector_dict, **ovo_fields)
            if self._connections is not None:
                self._connections.append(conn)
                self._ovo.volume_attachment.objects.append(conn._ovo)
            self._ovo.status = 'in-use'
            self.persistence.set_volume(self)
        except Exception:
            self._remove_export()
            # TODO: Improve raised exception
            raise
        return conn

    def _disconnect(self, connection):
        self._remove_export()
        if self._connections is not None:
            self._connections.remove(connection)
            self._ovo.volume_attachment.objects.remove(connection._ovo)

        if not self.connections:
            self._ovo.status = 'available'
            self.persistence.set_volume(self)

    def disconnect(self, connection, force=False):
        connection._disconnect(force)
        self._disconnect(connection)

    def cleanup(self):
        for attach in self.attachments:
            attach.detach()
        self._remove_export()

    def _remove_export(self):
        self.backend.driver.remove_export(self._context, self._ovo)


class Connection(Object):
    OVO_CLASS = volume_cmd.objects.VolumeAttachment

    @classmethod
    def connect(cls, volume, connector, *kwargs):
        conn_info = volume.backend.driver.initialize_connection(
            volume._ovo, connector)
        conn = cls(volume.backend,
                   connector=connector,
                   volume=volume,
                   status='attached',
                   attach_mode='rw',
                   connection_info=conn_info,
                   *kwargs)
        cls.persistence.set_connection(conn)
        return conn

    def __init__(self, *args, **kwargs):
        self.connected = True
        self._volume = kwargs.pop('volume')
        self.connector = kwargs.pop('connector', None)
        self.attach_info = kwargs.pop('attach_info', None)
        if '__ovo' not in kwargs:
            kwargs['volume'] = self._volume._ovo
            kwargs['volume_id'] = self._volume._ovo.id

        super(Connection, self).__init__(*args, **kwargs)

        self._populate_data()

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

    def _to_primitive(self):
        result = {
            'connector': self.connector,
        }

        if self.attach_info:
            attach_info = self.attach_info.copy()
            connector = attach_info['connector']
            attach_info['connector'] = {
                'use_multipath': connector.use_multipath,
                'device_scan_attempts': connector.device_scan_attempts,
            }
        else:
            attach_info = None
        result['attachment'] = attach_info
        return result

    def _populate_data(self):
        # Ensure circular reference is set
        self._ovo.volume = self.volume._ovo

        data = getattr(self._ovo, 'cinderlib_data', None)
        if data:
            self.connector = data.get('connector', None)
            self.attach_info = data.get('attachment', None)
        conn = (self.attach_info or {}).get('connector')
        if isinstance(conn, dict):
            self.attach_info['connector'] = utils.brick_get_connector(
                self.connection_info['driver_volume_type'],
                conn=self.connection_info,
                **conn)
        self.attached = bool(self.attach_info)

    def _replace_ovo(self, ovo):
        super(Connection, self)._replace_ovo(ovo)
        self._populate_data()

    @classmethod
    def _load(cls, backend, ovo):
        # Turn this around and do a Volume load
        volume = ovo.volume
        # Remove circular reference
        delattr(ovo, base_ovo._get_attrname('volume'))
        Volume._load(backend, volume)
        return Connection.objects[ovo.id]

    def _disconnect(self, force=False):
        self.backend.driver.terminate_connection(self._ovo.volume,
                                                 self.connector,
                                                 force=force)
        self.connected = False

        self._ovo.status = 'detached'
        self._ovo.deleted = True
        self.persistence.delete_connection(self)

    def disconnect(self, force=False):
        self._disconnect(force)
        self.volume._disconnect(self)

    def attach(self):
        self.attach_info = self.backend.driver._connect_device(
            self.connection_info)
        self.attached = True
        self.volume.local_attach = self

    def detach(self, force=False, ignore_errors=False, exc=None):
        if not exc:
            exc = brick_exception.ExceptionChainer()
        connector = self.attach_info['connector']
        with exc.context(force, 'Disconnect failed'):
            connector.disconnect_volume(self.connection_info['data'],
                                        self.attach_info['device'],
                                        force=force,
                                        ignore_errors=ignore_errors)
        self.attached = False
        self.volume.local_attach = None

        if exc and not ignore_errors:
            raise exc

    @property
    def path(self):
        if self.attach_info:
            return self.attach_info['device']['path']
        return None

    @classmethod
    def get_by_id(cls, connection_id):
        result = cls.persistence.get_connections(connection_id=connection_id)
        if not result:
            msg = 'id=%s' % connection_id
            raise exception.ConnectionNotFound(filter=msg)
        return result[0]

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self.volume.backend
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value


class Snapshot(NamedObject):
    OVO_CLASS = volume_cmd.objects.Snapshot
    DEFAULT_FIELDS_VALUES = {
        'status': 'creating',
        'metadata': {},
    }

    def __init__(self, volume, **kwargs):
        self._volume = volume

        if '__ovo' in kwargs:
            # Ensure circular reference is set if present
            if volume:
                kwargs['__ovo'].volume = volume._ovo
            backend = kwargs['__ovo']['progress']
        else:
            kwargs.setdefault('user_id', volume.user_id)
            kwargs.setdefault('project_id', volume.project_id)
            kwargs['volume_id'] = volume.id
            kwargs['volume_size'] = volume.size
            kwargs['volume_type_id'] = volume.volume_type_id
            kwargs['volume'] = volume._ovo
            if volume:
                backend = volume.backend.id
                kwargs['progress'] = backend

        super(Snapshot, self).__init__(backend=backend, **kwargs)

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

    @classmethod
    def _load(cls, backend, ovo):
        # Turn this around and do a Volume load
        volume = ovo.volume
        # Remove circular reference
        delattr(ovo, base_ovo._get_attrname('volume'))
        Volume._load(backend, volume)
        return Snapshot.objects[ovo.id]

    def _replace_ovo(self, ovo):
        super(Snapshot, self)._replace_ovo(ovo)
        # Ensure circular reference is set
        self._ovo.volume = self.volume._ovo

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
            self.persistence.set_snapshot(self)

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
        except Exception:
            new_vol._ovo.status = 'error'
            # TODO: raise with the new volume info
            raise
        finally:
            self.persistence.set_volume(new_vol)

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


setup = Object.setup
CONTEXT = Object.CONTEXT
