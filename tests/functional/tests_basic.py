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

import os
import tempfile

import base_tests


@base_tests.test_all_backends
class BackendFunctBasic(base_tests.BaseFunctTestCase):

    def test_stats(self):
        stats = self.backend.stats()
        self.assertIn('vendor_name', stats)
        self.assertIn('volume_backend_name', stats)
        pools_info = stats.get('pools', [stats])
        for pool_info in pools_info:
            self.assertIn('free_capacity_gb', pool_info)
            self.assertIn('total_capacity_gb', pool_info)

    def test_create_volume(self):
        self._create_vol(self.backend)
        # We are not testing delete, so leave the deletion to the tearDown

    def test_create_delete_volume(self):
        vol = self._create_vol(self.backend)

        vol.delete()
        self.assertEqual('deleted', vol.status)
        self.assertTrue(vol.deleted)
        self.assertNotIn(vol, self.backend.volumes)

        # Confirm idempotency of the operation by deleting it again
        vol._ovo.status = 'error'
        vol._ovo.deleted = False
        vol.delete()
        self.assertEqual('deleted', vol.status)
        self.assertTrue(vol.deleted)

    def test_create_snapshot(self):
        vol = self._create_vol(self.backend)
        self._create_snap(vol)
        # We are not testing delete, so leave the deletion to the tearDown

    def test_create_delete_snapshot(self):
        vol = self._create_vol(self.backend)
        snap = self._create_snap(vol)

        snap.delete()
        self.assertEqual('deleted', snap.status)
        self.assertTrue(snap.deleted)
        self.assertNotIn(snap, vol.snapshots)

        # Confirm idempotency of the operation by deleting it again
        snap._ovo.status = 'error'
        snap._ovo.deleted = False
        snap.delete()
        self.assertEqual('deleted', snap.status)
        self.assertTrue(snap.deleted)

    def test_attach_volume(self):
        vol = self._create_vol(self.backend)

        attach = vol.attach()
        path = attach.path

        self.assertIs(attach, vol.local_attach)
        self.assertIn(attach, vol.connections)

        self.assertTrue(os.path.exists(path))
        # We are not testing detach, so leave it to the tearDown

    def test_attach_detach_volume(self):
        vol = self._create_vol(self.backend)

        attach = vol.attach()
        self.assertIs(attach, vol.local_attach)
        self.assertIn(attach, vol.connections)

        vol.detach()
        self.assertIsNone(vol.local_attach)
        self.assertNotIn(attach, vol.connections)

    def test_attach_detach_volume_via_attachment(self):
        vol = self._create_vol(self.backend)

        attach = vol.attach()
        self.assertTrue(attach.attached)
        path = attach.path

        self.assertTrue(os.path.exists(path))

        attach.detach()
        self.assertFalse(attach.attached)
        self.assertIsNone(vol.local_attach)

        # We haven't disconnected the volume, just detached it
        self.assertIn(attach, vol.connections)

        attach.disconnect()
        self.assertNotIn(attach, vol.connections)

    def test_disk_io(self):
        data = '0123456789' * 100

        vol = self._create_vol(self.backend)

        attach = vol.attach()

        # TODO(geguileo: This will not work on Windows, for that we need to
        # pass delete=False and do the manual deletion ourselves.
        with tempfile.NamedTemporaryFile() as f:
            f.write(data)
            f.flush()
            self._root_execute('dd', 'if=' + f.name, of=attach.path)

        # Detach without removing the mapping of the volume since it's faster
        attach.detach()

        # Reattach, using old mapping, to validate data is there
        attach.attach()
        stdout = self._root_execute('dd', 'if=' + attach.path, count=1,
                                    ibs=len(data))

        self.assertEqual(data, stdout)
        vol.detach()

    def test_connect_disconnect_volume(self):
        # TODO(geguileo): Implement the test
        pass

    def test_connect_disconnect_multiple_volumes(self):
        # TODO(geguileo): Implement the test
        pass

    def test_connect_disconnect_multiple_times(self):
        # TODO(geguileo): Implement the test
        pass

    def test_stats_with_creation(self):
        # TODO(geguileo): Implement the test
        pass
