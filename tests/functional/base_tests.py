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

import functools
import os
import subprocess
import tempfile

import unittest2
import yaml

import cinderlib


def set_backend(func, new_name, backend_name):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self.backend = cinderlib.Backend.backends[backend_name]
        return func(self, *args, **kwargs)
    wrapper.__name__ = new_name
    wrapper.__wrapped__ = func
    return wrapper


def test_all_backends(cls):
    config = BaseFunctTestCase.ensure_config_loaded()
    for fname, func in cls.__dict__.items():
        if fname.startswith('test_'):
            for backend in config['backends']:
                bname = backend['volume_backend_name']
                test_name = '%s_on_%s' % (fname, bname)
                setattr(cls, test_name, set_backend(func, test_name, bname))
            delattr(cls, fname)
    return cls


class BaseFunctTestCase(unittest2.TestCase):
    DEFAULTS = {'logs': False, 'venv_sudo': False, 'size_precision': 0}
    FNULL = open(os.devnull, 'w')
    CONFIG_FILE = os.environ.get('CL_FTEST_CFG', 'tests/functional/lvm.yaml')
    tests_config = None

    @classmethod
    def ensure_config_loaded(cls):
        if not cls.tests_config:
            # Read backend configuration file
            with open(cls.CONFIG_FILE, 'r') as f:
                cls.tests_config = yaml.load(f)
            # Set configuration default values
            for k, v in cls.DEFAULTS.items():
                cls.tests_config.setdefault(k, v)
        return cls.tests_config

    @classmethod
    def setUpClass(cls):
        config = cls.ensure_config_loaded()

        if config['venv_sudo']:
            # NOTE(geguileo): For some drivers need to use a custom sudo script
            # to find virtualenv commands (ie: cinder-rtstool).
            path = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
            sudo_tool = os.path.join(path, '../../tools/virtualenv-sudo.sh')
            cls.root_helper = os.path.abspath(sudo_tool)
        else:
            cls.root_helper = 'sudo'
        cinderlib.setup(root_helper=cls.root_helper,
                        disable_logs=not config['logs'])

        # Initialize backends
        cls.backends = [cinderlib.Backend(**cfg) for cfg in
                        config['backends']]

        # Set current backend, by default is the first
        cls.backend = cls.backends[0]

        cls.size_precision = config['size_precision']

    @classmethod
    def tearDownClass(cls):
        errors = []
        # Do the cleanup of the resources the tests haven't cleaned up already
        for backend in cls.backends:
            # For each of the volumes that haven't been deleted delete the
            # snapshots that are still there and then the volume.
            # NOTE(geguileo): Don't use volumes and snapshots iterables since
            # they are modified when deleting.
            # NOTE(geguileo): Cleanup in reverse because RBD driver cannot
            # delete a snapshot that has a volume created from it.
            for vol in list(backend.volumes)[::-1]:
                for snap in list(vol.snapshots):
                    try:
                        snap.delete()
                    except Exception as exc:
                        errors.append('Error deleting snapshot %s from volume '
                                      '%s: %s' % (snap.id, vol.id, exc))
                # Detach if locally attached
                if vol.local_attach:
                    try:
                        vol.detach()
                    except Exception as exc:
                        errors.append('Error detaching %s for volume %s %s: '
                                      '%s' % (vol.local_attach.path, vol.id,
                                              exc))

                # Disconnect any existing connections
                for conn in vol.connections:
                    try:
                        conn.disconnect()
                    except Exception as exc:
                        errors.append('Error disconnecting volume %s: %s' %
                                      (vol.id, exc))

                try:
                    vol.delete()
                except Exception as exc:
                    errors.append('Error deleting volume %s: %s' %
                                  (vol.id, exc))
        if errors:
            raise Exception('Errors on test cleanup: %s' % '\n\t'.join(errors))

    def _root_execute(self, *args, **kwargs):
        cmd = [self.root_helper]
        cmd.extend(args)
        cmd.extend("%s=%s" % (k, v) for k, v in kwargs.items())
        return subprocess.check_output(cmd, stderr=self.FNULL)

    def _create_vol(self, backend=None, **kwargs):
        if not backend:
            backend = self.backend

        vol_size = kwargs.setdefault('size', 1)
        name = kwargs.setdefault('name', backend.id)

        vol = backend.create_volume(**kwargs)

        self.assertEqual('available', vol.status)
        self.assertEqual(vol_size, vol.size)
        self.assertEqual(name, vol.display_name)
        self.assertIn(vol, backend.volumes)
        return vol

    def _create_snap(self, vol, **kwargs):
        name = kwargs.setdefault('name', vol.id)

        snap = vol.create_snapshot(name=vol.id)

        self.assertEqual('available', snap.status)
        self.assertEqual(vol.size, snap.volume_size)
        self.assertEqual(name, snap.display_name)

        self.assertIn(snap, vol.snapshots)
        return snap

    def _get_vol_size(self, vol, do_detach=True):
        if not vol.local_attach:
            vol.attach()

        try:
            while True:
                try:
                    result = self._root_execute('lsblk', '-o', 'SIZE',
                                                '-b', vol.local_attach.path)
                    size_bytes = result.split()[1]
                    return float(size_bytes) / 1024.0 / 1024.0 / 1024.0
                # NOTE(geguileo): We can't catch subprocess.CalledProcessError
                # because somehow we get an instance from a different
                # subprocess.CalledProcessError class that isn't the same.
                except Exception as exc:
                    # If the volume is not yet available
                    if getattr(exc, 'returncode', 0) != 32:
                        raise
        finally:
            if do_detach:
                vol.detach()

    def _write_data(self, vol, data=None, do_detach=True):
        if not data:
            data = '0123456789' * 100

        if not vol.local_attach:
            vol.attach()

        # TODO(geguileo: This will not work on Windows, for that we need to
        # pass delete=False and do the manual deletion ourselves.
        try:
            with tempfile.NamedTemporaryFile() as f:
                f.write(data)
                f.flush()
                self._root_execute('dd', 'if=' + f.name,
                                   of=vol.local_attach.path)
        finally:
            if do_detach:
                vol.detach()

        return data

    def _read_data(self, vol, length, do_detach=True):
        if not vol.local_attach:
            vol.attach()
        try:
            stdout = self._root_execute('dd', 'if=' + vol.local_attach.path,
                                        count=1, ibs=length)
        finally:
            if do_detach:
                vol.detach()
        return stdout

    def _pools_info(self, stats):
        return stats.get('pools', [stats])

    def assertSize(self, expected_size, actual_size):
        if self.size_precision:
            self.assertAlmostEqual(expected_size, actual_size,
                                   self.size_precision)
        else:
            self.assertEqual(expected_size, actual_size)
