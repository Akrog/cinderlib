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
import json as json_lib
import logging
import os

from cinder import coordination
# NOTE(geguileo): If we want to prevent eventlet from monkey_patching we would
# need to do something about volume's L27-32.
# NOTE(geguileo): Probably a good idea not to depend on cinder.cmd.volume
# having all the other imports as they could change.
from cinder.cmd import volume as volume_cmd
from cinder import utils
from cinder.volume import configuration
import nos_brick
from oslo_utils import importutils
import urllib3

from cinderlib import objects
from cinderlib import persistence
from cinderlib import serialization


__all__ = ['setup', 'Backend']


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

    def __init__(self, volume_backend_name, **driver_cfg):
        if not self.global_initialization:
            self.global_setup()
        driver_cfg['volume_backend_name'] = volume_backend_name
        Backend.backends[volume_backend_name] = self

        conf = self._get_config(**driver_cfg)
        self.driver = importutils.import_object(
            conf.volume_driver,
            configuration=conf,
            db=self.persistence.db,
            host=volume_cmd.CONF.host,
            cluster_name=None,  # No clusters for now: volume_cmd.CONF.cluster,
            active_backend_id=None)  # No failover for now
        self.driver.do_setup(objects.CONTEXT)
        self.driver.check_for_setup_error()
        self.driver.init_capabilities()
        self.driver.set_throttle()
        self.driver.set_initialized()
        self._driver_cfg = driver_cfg
        self._volumes = None

    def __repr__(self):
        return '<cinderlib.Backend %s>' % self.id

    def __getattr__(self, name):
        return getattr(self.driver, name)

    @property
    def id(self):
        return self._driver_cfg['volume_backend_name']

    @property
    def volumes(self):
        if self._volumes is None:
            self._volumes = self.persistence.get_volumes(backend_name=self.id)
        return self._volumes

    def volumes_filtered(self, volume_id=None, volume_name=None):
        return self.persistence.get_volumes(backend_name=self.id,
                                            volume_id=volume_id,
                                            volume_name=volume_name)

    def stats(self, refresh=False):
        stats = self.driver.get_volume_stats(refresh=refresh)
        return stats

    def create_volume(self, size, name='', description='', bootable=False,
                      **kwargs):
        vol = objects.Volume(self, size=size, name=name,
                             description=description, bootable=bootable,
                             **kwargs)
        vol.create()
        return vol

    def _volume_removed(self, volume):
        if self._volumes:
            for i, vol in enumerate(self._volumes):
                if vol.id == volume.id:
                    del self._volumes[i]
                    break

    def _volume_created(self, volume):
        if self._volumes is not None:
            self._volumes.append(volume)

    def validate_connector(self, connector_dict):
        """Raise exception if missing info for volume's connect call."""
        self.driver.validate_connector(connector_dict)

    @classmethod
    def set_persistence(cls, persistence_config):
        if not hasattr(cls, 'project_id'):
            raise Exception('set_persistence can only be called after '
                            'cinderlib has been configured')
        cls.persistence = persistence.setup(persistence_config)
        objects.setup(cls.persistence, Backend, cls.project_id, cls.user_id,
                      cls.non_uuid_ids)
        for backend in cls.backends.values():
            backend.driver.db = cls.persistence.db

    @classmethod
    def global_setup(cls, file_locks_path=None, root_helper='sudo',
                     suppress_requests_ssl_warnings=True, disable_logs=True,
                     non_uuid_ids=False, output_all_backend_info=False,
                     project_id=None, user_id=None, persistence_config=None,
                     fail_on_missing_backend=True, **log_params):
        # Global setup can only be set once
        if cls.global_initialization:
            raise Exception('Already setup')

        cls.fail_on_missing_backend = fail_on_missing_backend
        cls.root_helper = root_helper
        cls.project_id = project_id
        cls.user_id = user_id
        cls.non_uuid_ids = non_uuid_ids

        cls.set_persistence(persistence_config)

        volume_cmd.CONF.version = volume_cmd.version.version_string()
        volume_cmd.CONF.register_opt(
            configuration.cfg.StrOpt('stateless_cinder'),
            group=configuration.SHARED_CONF_GROUP)

        serialization.setup(cls)

        cls._set_logging(disable_logs, **log_params)
        cls._set_priv_helper(root_helper)
        cls._set_coordinator(file_locks_path)

        if suppress_requests_ssl_warnings:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            urllib3.disable_warnings(
                urllib3.exceptions.InsecurePlatformWarning)

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
            volume_cmd.CONF.set_override(key, value)
        volume_cmd.logging.setup(volume_cmd.CONF, 'cinder')
        volume_cmd.python_logging.captureWarnings(True)

    @classmethod
    def _set_priv_helper(cls, root_helper):
        utils.get_root_helper = lambda: root_helper
        nos_brick.init(root_helper)

    @classmethod
    def _set_coordinator(cls, file_locks_path):
        file_locks_path = file_locks_path or os.getcwd()
        volume_cmd.CONF.set_override('lock_path', file_locks_path,
                                     'oslo_concurrency')
        volume_cmd.CONF.set_override('backend_url',
                                     'file://' + file_locks_path,
                                     'coordination')
        coordination.COORDINATOR.start()

    @property
    def config(self):
        if self.output_all_backend_info:
            return self._driver_cfg
        return {'volume_backend_name': self._driver_cfg['volume_backend_name']}

    def _serialize(self, property_name):
        result = [getattr(volume, property_name) for volume in self.volumes]
        # We only need to output the full backend configuration once
        if self.output_all_backend_info:
            backend = {'volume_backend_name': self.id}
            for volume in result:
                volume['backend'] = backend
        return {'class': type(self).__name__,
                'backend': self.config,
                'volumes': result}

    @property
    def json(self):
        return self._serialize('json')

    @property
    def dump(self):
        return self._serialize('dump')

    @property
    def jsons(self):
        return json_lib.dumps(self.json)

    @property
    def dumps(self):
        return json_lib.dumps(self.dump)

    @classmethod
    def load(cls, json_src, save=False):
        backend = Backend.load_backend(json_src['backend'])
        volumes = json_src.get('volumes')
        if volumes:
            backend._volumes = [objects.Volume.load(v, save) for v in volumes]
        return backend

    @classmethod
    def load_backend(cls, backend_data):
        backend_name = backend_data['volume_backend_name']
        if backend_name in cls.backends:
            return cls.backends[backend_name]

        if len(backend_data) > 1:
            return cls(**backend_data)

        if cls.fail_on_missing_backend:
            raise Exception('Backend not present in system or json.')

        return backend_name

    def refresh(self):
        if self._volumes is not None:
            self._volumes = None
            self.volumes


setup = Backend.global_setup
# Used by serialization.load
objects.Backend = Backend
# Needed if we use serialization.load before initializing cinderlib
objects.Object.backend_class = Backend
