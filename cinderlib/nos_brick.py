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
"""Helper code to attach/detach out of OpenStack

OS-Brick is meant to be used within OpenStack, which means that there are some
issues when using it on non OpenStack systems.

Here we take care of:

- Making sure we can work without privsep and using sudo directly
- Replacing an unlink privsep method that would run python code privileged
- Local attachment of RBD volumes using librados

Some of these changes may be later moved to OS-Brick. For now we just copied it
from the nos-brick repository.
"""
import functools
import os

from os_brick import exception
from os_brick.initiator import connector
from os_brick.initiator import connectors
from os_brick.privileged import rootwrap
from oslo_concurrency import processutils as putils
from oslo_privsep import priv_context
from oslo_utils import fileutils
from oslo_utils import strutils
import six


class RBDConnector(connectors.rbd.RBDConnector):
    """"Connector class to attach/detach RBD volumes locally.

    OS-Brick's implementation covers only 2 cases:

    - Local attachment on controller node.
    - Returning a file object on non controller nodes.

    We need a third one, local attachment on non controller node.
    """
    rbd_nbd_installed = True

    def connect_volume(self, connection_properties):
        # NOTE(e0ne): sanity check if ceph-common is installed.
        self._setup_rbd_methods()

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
            raise exception.BrickException(msg)

        conf = self._create_ceph_conf(monitor_ips, monitor_ports,
                                      str(cluster_name), user,
                                      keyring)
        dev_path = self._connect_volume(pool, volume, conf,
                                        connection_properties)

        return {'path': dev_path,
                'conf': conf,
                'type': 'block'}

    def _rbd_connect_volume(self, pool, volume, conf, connection_properties):
        # Map RBD volume if it's not already mapped
        dev_path = self.get_rbd_device_name(pool, volume)
        if (not os.path.islink(dev_path) or
                not os.path.exists(os.path.realpath(dev_path))):
            cmd = ['rbd', 'map', volume, '--pool', pool, '--conf', conf]
            cmd += self._get_rbd_args(connection_properties)
            self._execute(*cmd, root_helper=self._root_helper,
                          run_as_root=True)
        return os.path.realpath(dev_path)

    def _get_nbd_device_name(self, pool, volume, conf, connection_properties):
        cmd = ('rbd-nbd', 'list-mapped', '--conf', conf)
        cmd += self._get_rbd_args(connection_properties)
        stdout, stderr = self._execute(*cmd, root_helper=self._root_helper,
                                       run_as_root=True)
        for line in stdout.strip().splitlines():
            pid, dev_pool, image, snap, device = line.split(None)
            if dev_pool == pool and image == volume:
                return device
        return None

    def _nbd_connect_volume(self, pool, volume, conf, connection_properties):
        dev_path = self._get_nbd_device_name(pool, volume, conf,
                                             connection_properties)
        if not dev_path:
            cmd = ['rbd-nbd', 'map', volume, '--conf', conf]
            cmd += self._get_rbd_args(connection_properties)
            dev_path, stderr = self._execute(*cmd,
                                             root_helper=self._root_helper,
                                             run_as_root=True)
        return dev_path.strip()

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
        if self.rbd_nbd_installed:
            dev_path = self._get_nbd_device_name(pool, volume, conf_file,
                                                 connection_properties)
            executable = 'rbd-nbd'
        else:
            dev_path = self.get_rbd_device_name(pool, volume)
            executable = 'rbd'

        real_dev_path = os.path.realpath(dev_path)
        if os.path.exists(real_dev_path):
            cmd = [executable, 'unmap', dev_path, '--conf', conf_file]
            cmd += self._get_rbd_args(connection_properties)
            self._execute(*cmd, root_helper=self._root_helper,
                          run_as_root=True)
        fileutils.delete_if_exists(conf_file)

    def _check_installed(self):
        try:
            self._execute('which', 'rbd')
        except putils.ProcessExecutionError:
            msg = 'ceph-common package not installed'
            raise exception.BrickException(msg)

        try:
            self._execute('which', 'rbd-nbd')
            RBDConnector._connect_volume = RBDConnector._nbd_connect_volume
            RBDConnector._get_rbd_args = RBDConnector._get_nbd_args
        except putils.ProcessExecutionError:
            RBDConnector.rbd_nbd_installed = False

        # Don't check again to speed things on following connections
        RBDConnector.setup_rbd_methods = lambda *args: None

    def _get_nbd_args(self, connection_properties):
        return ('--id', connection_properties['auth_username'])

    _setup_rbd_methods = _check_installed
    _connect_volume = _rbd_connect_volume


ROOT_HELPER = 'sudo'


def unlink_root(*links, **kwargs):
    no_errors = kwargs.get('no_errors', False)
    raise_at_end = kwargs.get('raise_at_end', False)
    exc = exception.ExceptionChainer()
    catch_exception = no_errors or raise_at_end
    for link in links:
        with exc.context(catch_exception, 'Unlink failed for %s', link):
            putils.execute('unlink', link, run_as_root=True,
                           root_helper=ROOT_HELPER)
    if not no_errors and raise_at_end and exc:
        raise exc


def _execute(*cmd, **kwargs):
    try:
        return rootwrap.custom_execute(*cmd, **kwargs)
    except OSError as e:
        sanitized_cmd = strutils.mask_password(' '.join(cmd))
        raise putils.ProcessExecutionError(
            cmd=sanitized_cmd, description=six.text_type(e))


def init(root_helper='sudo'):
    global ROOT_HELPER
    ROOT_HELPER = root_helper
    priv_context.init(root_helper=[root_helper])

    existing_bgcp = connector.get_connector_properties
    existing_bcp = connector.InitiatorConnector.factory

    def my_bgcp(*args, **kwargs):
        if len(args):
            args = list(args)
            args[0] = ROOT_HELPER
        else:
            kwargs['root_helper'] = ROOT_HELPER
        kwargs['execute'] = _execute
        return existing_bgcp(*args, **kwargs)

    def my_bgc(protocol, *args, **kwargs):
        if len(args):
            # args is a tuple and we cannot do assignments
            args = list(args)
            args[0] = ROOT_HELPER
        else:
            kwargs['root_helper'] = ROOT_HELPER
        kwargs['execute'] = _execute

        # OS-Brick's implementation for RBD is not good enough for us
        if protocol == 'rbd':
            factory = RBDConnector
        else:
            factory = functools.partial(existing_bcp, protocol)

        return factory(*args, **kwargs)

    connector.get_connector_properties = my_bgcp
    connector.InitiatorConnector.factory = staticmethod(my_bgc)
    if hasattr(rootwrap, 'unlink_root'):
        rootwrap.unlink_root = unlink_root
