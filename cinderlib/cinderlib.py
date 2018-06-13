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
import functools
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
from oslo_utils import importutils

from os_brick import exception as brick_exception
from os_brick.initiator import connectors
from os_brick.privileged import rootwrap
from oslo_concurrency import processutils as putils
from oslo_utils import fileutils

import requests

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
                     **log_params):
        # Global setup can only be set once
        if cls.global_initialization:
            raise Exception('Already setup')

        # Prevent driver dynamic loading clearing configuration options
        volume_cmd.CONF._ConfigOpts__cache = MyDict()

        cls.root_helper = root_helper
        cls.project_id = project_id
        cls.user_id = user_id
        cls.non_uuid_ids = non_uuid_ids

        volume_cmd.CONF.version = volume_cmd.version.version_string()
        volume_cmd.CONF.register_opt(
            configuration.cfg.StrOpt('stateless_cinder'),
            group=configuration.SHARED_CONF_GROUP)

        cls.set_persistence(persistence_config)
        serialization.setup(cls)

        cls._set_logging(disable_logs, **log_params)
        cls._set_priv_helper(root_helper)
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

    @staticmethod
    def unlink_root(*links, **kwargs):
        no_errors = kwargs.get('no_errors', False)
        raise_at_end = kwargs.get('raise_at_end', False)
        exc = brick_exception.ExceptionChainer()
        catch_exception = no_errors or raise_at_end
        for link in links:
            with exc.context(catch_exception, 'Unlink failed for %s', link):
                putils.execute('unlink', link, run_as_root=True,
                               root_helper=Backend.root_helper)
        if not no_errors and raise_at_end and exc:
            raise exc

    @classmethod
    def _set_priv_helper(cls, root_helper):
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

        def my_bgc(protocol, *args, **kwargs):
            if len(args):
                # args is a tuple and we cannot do assignments
                args = list(args)
                args[0] = root_helper
            else:
                kwargs['root_helper'] = root_helper
            kwargs['execute'] = rootwrap.custom_execute

            # OS-Brick's implementation for RBD is not good enough for us
            if protocol == 'rbd':
                factory = RBDConnector
            else:
                factory = functools.partial(existing_bcp, protocol)

            return factory(*args, **kwargs)

        utils.connector.get_connector_properties = my_bgcp
        utils.connector.InitiatorConnector.factory = staticmethod(my_bgc)
        if hasattr(rootwrap, 'unlink_root'):
            rootwrap.unlink_root = cls.unlink_root

    @classmethod
    def _set_coordinator(cls, file_locks_path):
        file_locks_path = file_locks_path or os.getcwd()
        volume_cmd.CONF.oslo_concurrency.lock_path = file_locks_path
        volume_cmd.CONF.coordination.backend_url = 'file://' + file_locks_path
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

        raise Exception('Backend not present in system or json.')

    def refresh(self):
        if self._volumes is not None:
            self._volumes = None
            self.volumes


setup = Backend.global_setup
# Used by serialization.load
objects.Backend = Backend
# Needed if we use serialization.load before initializing cinderlib
objects.Object.backend_class = Backend


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


class RBDConnector(connectors.rbd.RBDConnector):
    """"Connector class to attach/detach RBD volumes locally.

    OS-Brick's implementation covers only 2 cases:

    - Local attachment on controller node.
    - Returning a file object on non controller nodes.

    We need a third one, local attachment on non controller node.
    """
    def connect_volume(self, connection_properties):
        # NOTE(e0ne): sanity check if ceph-common is installed.
        try:
            self._execute('which', 'rbd')
        except putils.ProcessExecutionError:
            msg = 'ceph-common package not installed'
            raise brick_exception.BrickException(msg)

        # Extract connection parameters and generate config file
        try:
            user = connection_properties['auth_username']
            pool, volume = connection_properties['name'].split('/')
            cluster_name = connection_properties.get('cluster_name')
            monitor_ips = connection_properties.get('hosts')
            monitor_ports = connection_properties.get('ports')
            keyring = connection_properties.get('keyring')
        except IndexError:
            msg = 'Malformed connection properties'
            raise brick_exception.BrickException(msg)

        conf = self._create_ceph_conf(monitor_ips, monitor_ports,
                                      str(cluster_name), user,
                                      keyring)

        # Map RBD volume if it's not already mapped
        rbd_dev_path = self.get_rbd_device_name(pool, volume)
        if (not os.path.islink(rbd_dev_path) or
                not os.path.exists(os.path.realpath(rbd_dev_path))):
            cmd = ['rbd', 'map', volume, '--pool', pool, '--conf', conf]
            cmd += self._get_rbd_args(connection_properties)
            self._execute(*cmd, root_helper=self._root_helper,
                          run_as_root=True)

        return {'path': os.path.realpath(rbd_dev_path),
                'conf': conf,
                'type': 'block'}

    def check_valid_device(self, path, run_as_root=True):
        """Verify an existing RBD handle is connected and valid."""
        try:
            self._execute('dd', 'if=' + path, 'of=/dev/null', 'bs=4096',
                          'count=1', root_helper=self._root_helper,
                          run_as_root=True)
        except putils.ProcessExecutionError:
            return False
        return True

    def disconnect_volume(self, connection_properties, device_info,
                          force=False, ignore_errors=False):

        pool, volume = connection_properties['name'].split('/')
        conf_file = device_info['conf']
        dev_name = self.get_rbd_device_name(pool, volume)
        cmd = ['rbd', 'unmap', dev_name, '--conf', conf_file]
        cmd += self._get_rbd_args(connection_properties)
        self._execute(*cmd, root_helper=self._root_helper,
                      run_as_root=True)
        fileutils.delete_if_exists(conf_file)
