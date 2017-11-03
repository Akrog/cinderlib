# Copyright (c) 2017, Red Hat, Inc.
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
import collections
import functools
import json as json_lib
import logging
import os
import requests
import uuid

from cinder import coordination
# NOTE(geguileo): If we want to prevent eventlet from monkey_patching we would
# need to do something about volume's L27-32.
# NOTE(geguileo): Provably a good idea not to depend on cinder.cmd.volume
# having all the other imports as they could change.
from cinder.cmd import volume as volume_cmd
from cinder import context
from cinder import exception
from cinder.objects import base as cinder_base_ovo
from cinder import utils
from cinder.volume import configuration
from oslo_utils import importutils
from oslo_versionedobjects import base as base_ovo
from os_brick import exception as brick_exception
from os_brick.privileged import rootwrap
import six


__all__ = ['setup', 'load', 'json', 'jsons', 'Backend', 'Volume', 'Snapshot',
           'Connection']


volume_cmd.objects.register_all()


class Backend(object):
    """Representation of a Cinder Driver.

    User facing attributes are:

    - __init__
    - json
    - jsons
    - load
    - stats
    - create_volume
    - global_setup
    - validate_connector
    """
    backends = {}
    global_initialization = False
    context = context.get_admin_context()

    def __init__(self, volume_backend_name, **driver_cfg):
        if not self.global_initialization:
            self.global_setup()
        driver_cfg['volume_backend_name'] = volume_backend_name
        Backend.backends[volume_backend_name] = self

        conf = self._get_config(**driver_cfg)
        self.driver = importutils.import_object(
            conf.volume_driver,
            configuration=conf,
            db=OVO.fake_db,
            host=volume_cmd.CONF.host,
            cluster_name=None,  # No clusters for now: volume_cmd.CONF.cluster,
            active_backend_id=None)  # No failover for now
        self.driver.do_setup(self.context)
        self.driver.check_for_setup_error()
        self.driver.init_capabilities()
        self.driver.set_throttle()
        self.driver.set_initialized()
        self.volumes = set()
        self._driver_cfg = driver_cfg

    def __repr__(self):
        return '<cinderlib.Backend %s>' % self.id

    def __getattr__(self, name):
        return getattr(self.driver, name)

    @property
    def id(self):
        return self._driver_cfg['volume_backend_name']

    @property
    def config(self):
        if self.output_all_backend_info:
            return self._driver_cfg
        return {'volume_backend_name': self._driver_cfg['volume_backend_name']}

    @property
    def json(self):
        result = [volume.json for volume in self.volumes]
        # We only need to output the full backend configuration once
        if self.output_all_backend_info:
            backend = {'volume_backend_name': self.id}
            for volume in result:
                volume['backend'] = backend
        return {'class': type(self).__name__,
                'backend': self.config,
                'volumes': result}

    @property
    def jsons(self):
        return json_lib.dumps(self.json)

    @classmethod
    def load(cls, json_src):
        backend = Backend.load_backend(json_src['backend'])
        for volume in json_src['volumes']:
            Volume.load(volume)
        return backend

    @classmethod
    def load_backend(cls, backend_data):
        backend_name = backend_data['volume_backend_name']
        if backend_name in cls.backends:
            return cls.backends[backend_name]

        if len(backend_data) > 1:
            return cls(**backend_data)

        raise Exception('Backend not present in system or json.')

    def stats(self, refresh=False):
        stats = self.driver.get_volume_stats(refresh=refresh)
        return stats

    def create_volume(self, size, name='', description='', bootable=False,
                      **kwargs):
        vol = Volume(self, size=size, name=name, description=description,
                     bootable=bootable, **kwargs)
        vol.create()
        return vol

    def validate_connector(self, connector_dict):
        """Raise exception if missing info for volume's connect call."""
        self.driver.validate_connector(connector_dict)

    @classmethod
    def global_setup(cls, file_locks_path=None, disable_sudo=False,
                     suppress_requests_ssl_warnings=True, disable_logs=True,
                     non_uuid_ids=False, output_all_backend_info=False,
                     **log_params):
        # Global setup can only be set once
        if cls.global_initialization:
            raise Exception('Already setup')

        # Prevent driver dynamic loading clearing configuration options
        volume_cmd.CONF._ConfigOpts__cache = MyDict()

        volume_cmd.CONF.version = volume_cmd.version.version_string()
        volume_cmd.CONF.register_opt(
            configuration.cfg.StrOpt('stateless_cinder'),
            group=configuration.SHARED_CONF_GROUP)

        OVO._ovo_init(non_uuid_ids)

        cls._set_logging(disable_logs, **log_params)
        cls._set_priv_helper()
        cls._set_coordinator(file_locks_path)

        if suppress_requests_ssl_warnings:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning)
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecurePlatformWarning)

        cls.global_initialization = True
        cls.output_all_backend_info = output_all_backend_info

    def _get_config(self, volume_backend_name, **kwargs):
        volume_cmd.CONF.register_opt(volume_cmd.host_opt,
                                     group=volume_backend_name)
        backend_opts = getattr(volume_cmd.CONF, volume_backend_name)
        for key, value in kwargs.items():
            setattr(backend_opts, key, value)
        config = configuration.Configuration([],
                                             config_group=volume_backend_name)
        return config

    @classmethod
    def _set_logging(cls, disable_logs, **log_params):
        if disable_logs:
            logging.Logger.disabled = property(lambda s: True,
                                               lambda s, x: None)
            return

        for key, value in log_params.items():
            setattr(volume_cmd.CONF, key, value)
        volume_cmd.logging.setup(volume_cmd.CONF, 'cinder')
        volume_cmd.python_logging.captureWarnings(True)

    @classmethod
    def _set_priv_helper(cls):
        root_helper = 'sudo'
        utils.get_root_helper = lambda: root_helper
        volume_cmd.priv_context.init(root_helper=[root_helper])

        existing_bgcp = utils.connector.get_connector_properties
        existing_bcp = utils.connector.InitiatorConnector.factory

        def my_bgcp(*args, **kwargs):
            if len(args):
                args = list(args)
                args[0] = root_helper
            else:
                kwargs['root_helper'] = root_helper
            kwargs['execute'] = rootwrap.custom_execute
            return existing_bgcp(*args, **kwargs)

        def my_bgc(*args, **kwargs):
            if len(args) >= 2:
                args = list(args)
                args[1] = root_helper
            else:
                kwargs['root_helper'] = root_helper
            kwargs['execute'] = rootwrap.custom_execute
            return existing_bcp(*args, **kwargs)

        utils.connector.get_connector_properties = my_bgcp
        utils.connector.InitiatorConnector.factory = staticmethod(my_bgc)

    @classmethod
    def _set_coordinator(cls, file_locks_path):
        file_locks_path = file_locks_path or os.getcwd()
        volume_cmd.CONF.oslo_concurrency.lock_path = file_locks_path
        volume_cmd.CONF.coordination.backend_url = 'file://' + file_locks_path
        coordination.COORDINATOR.start()


setup = Backend.global_setup


def load(json_src):
    """Load any json serialized cinderlib object."""
    if isinstance(json_src, six.string_types):
        json_src = json_lib.loads(json_src)

    if isinstance(json_src, list):
        return [globals()[obj['class']].load(obj) for obj in json_src]

    return globals()[json_src['class']].load(json_src)


def json():
    """Conver to Json everything we have in this system."""
    return [backend.json for backend in Backend.backends.values()]


def jsons():
    """Convert to a Json string everything we have in this system."""
    return json_lib.dumps(json())


class Object(object):
    """Base class for our resource representation objects."""
    DEFAULT_FIELDS_VALUES = {}
    objects = collections.defaultdict(dict)
    context = context.get_admin_context()

    def __init__(self, backend, **fields_data):
        self.backend = backend

        __ovo = fields_data.get('__ovo')
        if __ovo:
            self._ovo = __ovo
        else:
            self._ovo = self._create_ovo(**fields_data)

        cls = type(self)
        cls.objects = Object.objects[cls.__name__]
        # TODO: Don't replace if present is newer
        self.objects[self._ovo.id] = self

    def _to_primitive(self):
        return None

    def _create_ovo(self, **fields_data):
        # The base are the default values we define on our own classes
        fields_values = self.DEFAULT_FIELDS_VALUES.copy()

        # Apply the values defined by the caller
        fields_values.update(fields_data)

        # We support manually setting the id, so set only if not already set
        fields_values.setdefault('id', self.new_uuid())

        # Set non set field values based on OVO's default value and on whether
        # it is nullable or not.
        for field_name, field in self.OVO_CLASS.fields.items():
            if field.default != cinder_base_ovo.fields.UnspecifiedDefault:
                fields_values.setdefault(field_name, field.default)
            elif field.nullable:
                fields_values.setdefault(field_name, None)

        return self.OVO_CLASS(context=self.context, **fields_values)

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
        backend = Backend.load_backend(json_src['backend'])

        backend_name = json_src['backend']['volume_backend_name']
        if backend_name in Backend.backends:
            backend = Backend.backends[backend_name]
        elif len(json_src['backend']) == 1:
            raise Exception('Backend not present in system or json.')
        else:
            backend = Backend(**json_src['backend'])

        ovo = cinder_base_ovo.CinderObject.obj_from_primitive(json_src['ovo'],
                                                              cls.context)
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


class Volume(Object):
    OVO_CLASS = volume_cmd.objects.Volume
    DEFAULT_FIELDS_VALUES = {
        'size': 1,
        'user_id': Object.context.user_id,
        'project_id': Object.context.project_id,
        'host': volume_cmd.CONF.host,
        'status': 'creating',
        'attach_status': 'detached',
        'metadata': {},
        'admin_metadata': {},
        'glance_metadata': {},
    }

    _ignore_keys = ('id', 'volume_attachment' 'snapshots')

    def __init__(self, backend_or_vol, **kwargs):
        # Accept a volume as additional source data
        if isinstance(backend_or_vol, Volume):
            for key in backend_or_vol._ovo.fields:
                if (backend_or_vol._ovo.obj_attr_is_set(key) and
                        key not in self._ignore_keys):
                    kwargs.setdefault(key, getattr(backend_or_vol._ovo, key))
            backend_or_vol = backend_or_vol.backend

        if '__ovo' not in kwargs:
            if 'description' in kwargs:
                kwargs['display_description'] = kwargs.pop('description')
            if 'name' in kwargs:
                kwargs['display_name'] = kwargs.pop('name')
            kwargs.setdefault(
                'volume_attachment',
                volume_cmd.objects.VolumeAttachmentList(context=self.context))
            kwargs.setdefault(
                'snapshots',
                volume_cmd.objects.SnapshotList(context=self.context))

        super(Volume, self).__init__(backend_or_vol, **kwargs)
        self.snapshots = set()
        self.connections = []
        self._populate_data()
        self.backend.volumes.add(self)

    def _to_primitive(self):
        local_attach = self.local_attach.id if self.local_attach else None
        return {'local_attach': local_attach,
                'exported': self.exported}

    @classmethod
    def _load(cls, backend, ovo):
        # Restore snapshot's circular reference removed on serialization
        for snap in ovo.snapshots:
            snap.volume = ovo

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
        old_snapshots = {snap.id: snap for snap in self.snapshots}

        for snap_ovo in self._ovo.snapshots:
            snap = Object.objects['Snapshot'].get(snap_ovo.id)
            if snap:
                snap._replace_ovo(snap_ovo)
                del old_snapshots[snap.id]
            else:
                snap = Snapshot(self, __ovo=snap_ovo)
                self.snapshots.add(snap)

        for snap_id, snap in old_snapshots.items():
            self.snapshots.discard(snap)
            # We leave snapshots in the global DB just in case...
            # del Object.objects['Snapshot'][snap_id]

        old_connections = {conn.id: conn for conn in self.connections}

        for conn_ovo in self._ovo.volume_attachment:
            conn = Object.objects['Connection'].get(conn_ovo.id)
            if conn:
                conn._replace_ovo(conn_ovo)
                del old_connections[conn.id]
            else:
                conn = Connection(self.backend, volume=self, __ovo=conn_ovo)
                self.connections.append(conn)

        for conn_id, conn in old_connections.items():
            self.connections.remove(conn)
            # We leave connections in the global DB just in case...
            # del Object.objects['Connection'][conn_id]

        data = getattr(self._ovo, 'cinderlib_data', {})
        self.exported = data.get('exported', False)
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

    def delete(self):
        # Some backends delete existing snapshots while others leave them
        try:
            self.backend.driver.delete_volume(self._ovo)
            self._ovo.status = 'deleted'
            self._ovo.deleted = True
            # volume.deleted_at =
        except Exception:
            self._ovo.status = 'error'
            # TODO: raise with the vol info
            raise
        self.backend.volumes.discard(self)

    def extend(self, size):
        volume = self._ovo
        volume.previous_status = volume.status
        volume.status = 'extending'
        try:
            self.backend.driver.extend_volume(volume, size)
        except Exception:
            volume.status = 'error'
            # TODO: raise with the vol info
            raise

        volume.size = size
        volume.status = volume.previous_status
        volume.previous_status = None

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
        return new_vol

    def create_snapshot(self, name='', description='', **kwargs):
        snap = Snapshot(self, name=name, description=description, **kwargs)
        snap.create()
        self.snapshots.add(snap)
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

    def connect(self, connector_dict):
        if not self.exported:
            model_update = self.backend.driver.create_export(self.context,
                                                             self._ovo,
                                                             connector_dict)
            if model_update:
                self._ovo.update(model_update)
            self.exported = True

        try:
            conn = Connection.connect(self, connector_dict)
            self.connections.append(conn)
            self._ovo.status = 'in-use'
        except Exception:
            if not self.connections:
                self._remove_export()
            # TODO: Improve raised exception
            raise
        return conn

    def _disconnect(self, connection):
        self.connections.remove(connection)
        if not self.connections:
            self._remove_export()
            self._ovo.status = 'available'

    def disconnect(self, connection, force=False):
        connection._disconnect(force)
        self._disconnect(connection)

    def cleanup(self):
        for attach in self.attachments:
            attach.detach()
        self._remove_export()

    def _remove_export(self):
        self.backend.driver.remove_export(self._context, self._ovo)
        self.exported = False


class Connection(Object):
    OVO_CLASS = volume_cmd.objects.VolumeAttachment

    @classmethod
    def connect(cls, volume, connector):
        conn_info = volume.backend.driver.initialize_connection(
            volume._ovo, connector)
        conn = cls(volume.backend,
                   connector=connector,
                   volume=volume,
                   status='attached',
                   attach_mode='rw',
                   connection_info=conn_info)
        volume._ovo.volume_attachment.objects.append(conn._ovo)
        return conn

    def __init__(self, *args, **kwargs):
        self.connected = True
        self.volume = kwargs.pop('volume')
        self.connector = kwargs.pop('connector', None)
        self.attach_info = kwargs.pop('attach_info', None)
        if '__ovo' not in kwargs:
            kwargs['volume'] = self.volume._ovo
            kwargs['volume_id'] = self.volume._ovo.id

        super(Connection, self).__init__(*args, **kwargs)

        self._populate_data()

    def _to_primitive(self):
        attach_info = self.attach_info.copy()
        connector = self.attach_info['connector']
        attach_info['connector'] = {
            'use_multipath': connector.use_multipath,
            'device_scan_attempts': connector.device_scan_attempts,
        }

        return {'connector': self.connector,
                'attach_info': attach_info}

    def _populate_data(self):
        # Ensure circular reference is set
        self._ovo.volume = self.volume._ovo

        data = getattr(self._ovo, 'cinderlib_data', None)
        if data:
            self.connector = data.get('connector', None)
            self.attach_info = data.get('attach_info', None)
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
        volume.volume_attachment.objects.append(ovo)
        # Remove circular reference
        delattr(ovo, base_ovo._get_attrname('volume'))
        Volume._load(backend, volume)
        return Connection.objects[ovo.id]

    def _disconnect(self, force=False):
        self.backend.driver.terminate_connection(self._ovo.volume,
                                                 self.connector,
                                                 force=force)
        self.connected = False

        self._ovo.volume.volume_attachment.objects.remove(self._ovo)
        self._ovo.status = 'detached'
        self._ovo.deleted = True

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


class Snapshot(Object):
    OVO_CLASS = volume_cmd.objects.Snapshot
    DEFAULT_FIELDS_VALUES = {
        'status': 'creating',
        'metadata': {},
    }

    def __init__(self, volume, **kwargs):
        self.volume = volume
        if '__ovo' in kwargs:
            # Ensure circular reference is set
            kwargs['__ovo'].volume = volume._ovo
        else:
            kwargs.setdefault('user_id', volume.user_id)
            kwargs.setdefault('project_id', volume.project_id)
            kwargs['volume_id'] = volume.id
            kwargs['volume_size'] = volume.size
            kwargs['volume_type_id'] = volume.volume_type_id
            kwargs['volume'] = volume._ovo

            if 'description' in kwargs:
                kwargs['display_description'] = kwargs.pop('description')
            if 'name' in kwargs:
                kwargs['display_name'] = kwargs.pop('name')

        super(Snapshot, self).__init__(volume.backend, **kwargs)

    @classmethod
    def _load(cls, backend, ovo):
        # Turn this around and do a Volume load
        volume = ovo.volume
        volume.snapshots.objects.append(ovo)
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

    def delete(self):
        try:
            self.backend.driver.delete_snapshot(self._ovo)
            self._ovo.status = 'deleted'
            self._ovo.deleted = True
            # snapshot.deleted_at =
        except Exception:
            self._ovo.status = 'error'
            # TODO: raise with the snap info
            raise
        self.volume.snapshots.discard(self)
        try:
            self.volume._ovo.snapshots.objects.remove(self._ovo)
        except ValueError:
            pass

    def create_volume(self, **new_vol_params):
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
        return new_vol


class OVO(object):
    """Oslo Versioned Objects helper class.

    Class will prevent OVOs from actually trying to save to the DB on request,
    replace some 'get_by_id' methods to prevent them from going to the DB while
    still returned the expected data, remove circular references when saving
    objects (for example in a Volume OVO it has a 'snapshot' field which is a
    Snapshot OVO that has a 'volume' back reference), piggy back on the OVO's
    serialization mechanism to add/get additional data we want.
    """
    OBJ_NAME_MAPS = {'VolumeAttachment': 'Connection'}

    @classmethod
    def _ovo_init(cls, non_uuid_ids):
        # Create fake DB for drivers
        cls.fake_db = DB()

        # Replace the standard DB configuration for code that doesn't use the
        # driver.db attribute (ie: OVOs).
        volume_cmd.session.IMPL = cls.fake_db

        # Replace get_by_id methods with something that will return expected
        # data
        volume_cmd.objects.Volume.get_by_id = DB.volume_get
        volume_cmd.objects.Snapshot.get_by_id = DB.snapshot_get

        # Use custom dehydration methods that prevent maximum recursion errors
        # due to circular references:
        #   ie: snapshot -> volume -> snapshots -> snapshot
        base_ovo.VersionedObject.obj_to_primitive = cls.obj_to_primitive
        cinder_base_ovo.CinderObject.obj_from_primitive = classmethod(
            cls.obj_from_primitive)

        fields = base_ovo.obj_fields
        fields.Object.to_primitive = staticmethod(cls.field_ovo_to_primitive)
        fields.Field.to_primitive = cls.field_to_primitive
        fields.List.to_primitive = cls.iterable_to_primitive
        fields.Set.to_primitive = cls.iterable_to_primitive
        fields.Dict.to_primitive = cls.dict_to_primitive
        cls.wrap_to_primitive(fields.FieldType)
        cls.wrap_to_primitive(fields.DateTime)
        cls.wrap_to_primitive(fields.IPAddress)

        # Disable saving in ovos
        for ovo_name in cinder_base_ovo.CinderObjectRegistry.obj_classes():
            ovo_cls = getattr(volume_cmd.objects, ovo_name)
            ovo_cls.save = lambda *args, **kwargs: None
            if non_uuid_ids and 'id' in ovo_cls.fields:
                ovo_cls.fields['id'] = cinder_base_ovo.fields.StringField()

    @staticmethod
    def wrap_to_primitive(cls):
        method = getattr(cls, 'to_primitive')

        @functools.wraps(method)
        def to_primitive(obj, attr, value, visited=None):
            return method(obj, attr, value)
        setattr(cls, 'to_primitive', staticmethod(to_primitive))

    @staticmethod
    def obj_to_primitive(self, target_version=None, version_manifest=None,
                         visited=None):
        # No target_version, version_manifest, or changes support
        if visited is None:
            visited = set()
        visited.add(id(self))

        primitive = {}
        for name, field in self.fields.items():
            if self.obj_attr_is_set(name):
                value = getattr(self, name)
                # Skip cycles
                if id(value) in visited:
                    continue
                primitive[name] = field.to_primitive(self, name, value,
                                                     visited)

        obj_name = self.obj_name()
        obj = {
            self._obj_primitive_key('name'): obj_name,
            self._obj_primitive_key('namespace'): self.OBJ_PROJECT_NAMESPACE,
            self._obj_primitive_key('version'): self.VERSION,
            self._obj_primitive_key('data'): primitive
        }

        # Piggyback to store our own data
        my_obj_name = OVO.OBJ_NAME_MAPS.get(obj_name, obj_name)
        if 'id' in primitive and my_obj_name in Object.objects:
            my_obj = Object.objects[my_obj_name][primitive['id']]
            obj['cinderlib.data'] = my_obj._to_primitive()

        return obj

    @staticmethod
    def obj_from_primitive(
            cls, primitive, context=None,
            original_method=cinder_base_ovo.CinderObject.obj_from_primitive):
        result = original_method(primitive, context)
        result.cinderlib_data = primitive.get('cinderlib.data')
        return result

    @staticmethod
    def field_ovo_to_primitive(obj, attr, value, visited=None):
        return value.obj_to_primitive(visited=visited)

    @staticmethod
    def field_to_primitive(self, obj, attr, value, visited=None):
        if value is None:
            return None
        return self._type.to_primitive(obj, attr, value, visited)

    @staticmethod
    def iterable_to_primitive(self, obj, attr, value, visited=None):
        if visited is None:
            visited = set()
        visited.add(id(value))
        result = []
        for elem in value:
            if id(elem) in visited:
                continue
            visited.add(id(elem))
            r = self._element_type.to_primitive(obj, attr, elem, visited)
            result.append(r)
        return result

    @staticmethod
    def dict_to_primitive(self, obj, attr, value, visited=None):
        if visited is None:
            visited = set()
        visited.add(id(value))

        primitive = {}
        for key, elem in value.items():
            if id(elem) in visited:
                continue
            visited.add(id(elem))
            primitive[key] = self._element_type.to_primitive(
                obj, '%s["%s"]' % (attr, key), elem, visited)
        return primitive


class DB(object):
    """Replacement for DB access methods.

    This will serve as replacement for methods used by:

    - Drivers
    - OVOs' get_by_id method
    - DB implementation

    Data will be retrieved based on the objects we store in our own Volume
    and Snapshots classes.
    """

    @classmethod
    def volume_get(cls, context, volume_id, *args, **kwargs):
        if volume_id not in Volume.objects:
            raise exception.VolumeNotFound(volume_id=volume_id)
        return Volume.objects[volume_id]._ovo

    @classmethod
    def snapshot_get(cls, context, snapshot_id, *args, **kwargs):
        if snapshot_id not in Snapshot.objects:
            raise exception.SnapshotNotFound(snapshot_id=snapshot_id)
        return Snapshot.objects[snapshot_id]._ovo


class MyDict(dict):
    """Custom non clearable dictionary.

    Required to overcome the nature of oslo.config where configuration comes
    from files and command line input.

    Using this dictionary we can load from memory everything and it won't clear
    things when we dynamically load a driver and the driver has new
    configuration options.
    """
    def clear(self):
        pass
