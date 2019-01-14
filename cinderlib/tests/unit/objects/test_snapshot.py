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

import mock

from cinderlib import exception
from cinderlib import objects
from cinderlib.tests.unit import base


class TestSnapshot(base.BaseTest):
    def setUp(self):
        super(TestSnapshot, self).setUp()
        self.vol = objects.Volume(self.backend_name, size=10,
                                  extra_specs={'e': 'v'},
                                  qos_specs={'q': 'qv'})
        self.snap = objects.Snapshot(self.vol,
                                     name='my_snap', description='my_desc')
        self.vol._snapshots.append(self.snap)
        self.vol._ovo.snapshots.objects.append(self.snap._ovo)

    def test_init_from_volume(self):
        self.assertIsNotNone(self.snap.id)
        self.assertEqual(self.backend, self.snap.backend)
        self.assertEqual('my_snap', self.snap.name)
        self.assertEqual('my_snap', self.snap.display_name)
        self.assertEqual('my_desc', self.snap.description)
        self.assertEqual(self.vol.user_id, self.snap.user_id)
        self.assertEqual(self.vol.project_id, self.snap.project_id)
        self.assertEqual(self.vol.id, self.snap.volume_id)
        self.assertEqual(self.vol.size, self.snap.volume_size)
        self.assertEqual(self.vol._ovo, self.snap._ovo.volume)
        self.assertEqual(self.vol.volume_type_id, self.snap.volume_type_id)
        self.assertEqual(self.vol, self.snap.volume)

    def test_init_from_ovo(self):
        snap2 = objects.Snapshot(None, __ovo=self.snap._ovo)
        self.assertEqual(self.snap.backend, snap2.backend)
        self.assertEqual(self.snap._ovo, snap2._ovo)
        self.assertEqual(self.vol, self.snap.volume)

    def test_create(self):
        update_vol = {'provider_id': 'provider_id'}
        self.backend.driver.create_snapshot.return_value = update_vol
        self.snap.create()
        self.assertEqual('available', self.snap.status)
        self.assertEqual('provider_id', self.snap.provider_id)
        self.backend.driver.create_snapshot.assert_called_once_with(
            self.snap._ovo)
        self.persistence.set_snapshot.assert_called_once_with(self.snap)

    def test_create_error(self):
        self.backend.driver.create_snapshot.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            self.snap.create()

        self.assertEqual(self.snap, assert_context.exception.resource)
        self.backend.driver.create_snapshot.assert_called_once_with(
            self.snap._ovo)
        self.assertEqual('error', self.snap.status)
        self.persistence.set_snapshot.assert_called_once_with(self.snap)

    def test_delete(self):
        self.snap.delete()
        self.backend.driver.delete_snapshot.assert_called_once_with(
            self.snap._ovo)
        self.persistence.delete_snapshot.assert_called_once_with(self.snap)
        self.assertEqual([], self.vol.snapshots)
        self.assertEqual([], self.vol._ovo.snapshots.objects)
        self.assertEqual('deleted', self.snap.status)

    def test_delete_error(self):
        self.backend.driver.delete_snapshot.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            self.snap.delete()
        self.assertEqual(self.snap, assert_context.exception.resource)
        self.backend.driver.delete_snapshot.assert_called_once_with(
            self.snap._ovo)
        self.persistence.delete_snapshot.assert_not_called()
        self.assertEqual([self.snap], self.vol.snapshots)
        self.assertEqual([self.snap._ovo], self.vol._ovo.snapshots.objects)
        self.assertEqual('error_deleting', self.snap.status)

    def test_create_volume(self):
        create_mock = self.backend.driver.create_volume_from_snapshot
        create_mock.return_value = None
        vol2 = self.snap.create_volume(name='new_name', description='new_desc')
        create_mock.assert_called_once_with(vol2._ovo, self.snap._ovo)
        self.assertEqual('available', vol2.status)
        self.assertEqual(1, len(self.backend._volumes))
        self.assertEqual(vol2, self.backend._volumes[0])
        self.persistence.set_volume.assert_called_once_with(vol2)
        self.assertEqual(self.vol.id, self.vol.volume_type_id)
        self.assertNotEqual(self.vol.id, vol2.id)
        self.assertEqual(vol2.id, vol2.volume_type_id)
        self.assertEqual(self.vol.volume_type.extra_specs,
                         vol2.volume_type.extra_specs)
        self.assertEqual(self.vol.volume_type.qos_specs.specs,
                         vol2.volume_type.qos_specs.specs)

    def test_create_volume_error(self):
        create_mock = self.backend.driver.create_volume_from_snapshot
        create_mock.side_effect = exception.NotFound
        with self.assertRaises(exception.NotFound) as assert_context:
            self.snap.create_volume()
        self.assertEqual(1, len(self.backend._volumes_inflight))
        vol2 = list(self.backend._volumes_inflight.values())[0]
        self.assertEqual(vol2, assert_context.exception.resource)
        create_mock.assert_called_once_with(vol2, self.snap._ovo)
        self.assertEqual('error', vol2.status)
        self.persistence.set_volume.assert_called_once_with(mock.ANY)

    def test_get_by_id(self):
        mock_get_snaps = self.persistence.get_snapshots
        mock_get_snaps.return_value = [mock.sentinel.snap]
        res = objects.Snapshot.get_by_id(mock.sentinel.snap_id)
        mock_get_snaps.assert_called_once_with(
            snapshot_id=mock.sentinel.snap_id)
        self.assertEqual(mock.sentinel.snap, res)

    def test_get_by_id_not_found(self):
        mock_get_snaps = self.persistence.get_snapshots
        mock_get_snaps.return_value = None
        self.assertRaises(exception.SnapshotNotFound,
                          objects.Snapshot.get_by_id, mock.sentinel.snap_id)
        mock_get_snaps.assert_called_once_with(
            snapshot_id=mock.sentinel.snap_id)

    def test_get_by_name(self):
        res = objects.Snapshot.get_by_name(mock.sentinel.name)
        mock_get_snaps = self.persistence.get_snapshots
        mock_get_snaps.assert_called_once_with(
            snapshot_name=mock.sentinel.name)
        self.assertEqual(mock_get_snaps.return_value, res)
