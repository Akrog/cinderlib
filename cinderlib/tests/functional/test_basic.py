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

import base_tests


@base_tests.test_all_backends
class BackendFunctBasic(base_tests.BaseFunctTestCase):

    def test_stats(self):
        stats = self.backend.stats()
        self.assertIn('vendor_name', stats)
        self.assertIn('volume_backend_name', stats)
        pools_info = self._pools_info(stats)
        for pool_info in pools_info:
            self.assertIn('free_capacity_gb', pool_info)
            self.assertIn('total_capacity_gb', pool_info)

    def _volumes_in_pools(self, pools_info):
        if not any('total_volumes' in p for p in pools_info):
            return None
        return sum(p.get('total_volumes', 0) for p in pools_info)

    def test_stats_with_creation(self):
        # This test can fail if we are don't have exclusive usage of the
        # storage pool used in the tests or if the specific driver does not
        # return the right values in allocated_capacity_gb or
        # provisioned_capacity_gb.
        initial_stats = self.backend.stats(refresh=True)
        vol = self._create_vol(self.backend)
        new_stats = self.backend.stats(refresh=True)

        initial_pools_info = self._pools_info(initial_stats)
        new_pools_info = self._pools_info(new_stats)

        initial_volumes = self._volumes_in_pools(initial_pools_info)
        new_volumes = self._volumes_in_pools(new_pools_info)

        # If the backend is reporting the number of volumes, check them
        if initial_volumes is not None:
            self.assertEqual(initial_volumes + 1, new_volumes)

        initial_size = sum(p.get('allocated_capacity_gb',
                                 p.get('provisioned_capacity_gb', 0))
                           for p in initial_pools_info)
        new_size = sum(p.get('allocated_capacity_gb',
                             p.get('provisioned_capacity_gb', vol.size))
                       for p in new_pools_info)
        self.assertEqual(initial_size + vol.size, new_size)

    def test_create_volume(self):
        vol = self._create_vol(self.backend)
        vol_size = self._get_vol_size(vol)
        self.assertSize(vol.size, vol_size)
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
        vol = self._create_vol(self.backend)
        data = self._write_data(vol)

        read_data = self._read_data(vol, len(data))

        self.assertEqual(data, read_data)

    def test_extend(self):
        vol = self._create_vol(self.backend)
        original_size = vol.size
        result_original_size = self._get_vol_size(vol)
        self.assertSize(original_size, result_original_size)

        new_size = vol.size + 1
        vol.extend(new_size)

        self.assertEqual(new_size, vol.size)
        result_new_size = self._get_vol_size(vol)
        self.assertSize(new_size, result_new_size)

    def test_clone(self):
        vol = self._create_vol(self.backend)
        original_size = self._get_vol_size(vol, do_detach=False)
        data = self._write_data(vol)

        new_vol = vol.clone()
        self.assertEqual(vol.size, new_vol.size)

        cloned_size = self._get_vol_size(new_vol, do_detach=False)
        read_data = self._read_data(new_vol, len(data))
        self.assertEqual(original_size, cloned_size)
        self.assertEqual(data, read_data)

    def test_create_volume_from_snapshot(self):
        # Create a volume and write some data
        vol = self._create_vol(self.backend)
        original_size = self._get_vol_size(vol, do_detach=False)
        data = self._write_data(vol)

        # Take a snapshot
        snap = vol.create_snapshot()
        self.assertEqual(vol.size, snap.volume_size)

        # Change the data in the volume
        reversed_data = data[::-1]
        self._write_data(vol, data=reversed_data)

        # Create a new volume from the snapshot with the original data
        new_vol = snap.create_volume()
        self.assertEqual(vol.size, new_vol.size)

        created_size = self._get_vol_size(new_vol, do_detach=False)
        read_data = self._read_data(new_vol, len(data))
        self.assertEqual(original_size, created_size)
        self.assertEqual(data, read_data)
