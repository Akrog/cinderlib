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

import unittest2

import cinderlib
from tests.unit import utils


class TestMemoryPersistence(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        # We check the entrypoint is working
        cls.persistence = cinderlib.persistence.setup({'storage': 'memory'})
        cinderlib.objects.Object.setup(cls.persistence, cinderlib.Backend,
                                       None, None, False)

    def setUp(self):
        self.backend = utils.FakeBackend()

        # Since this plugin uses class attributes we have to clear them
        self.persistence.volumes = {}
        self.persistence.snapshots = {}
        self.persistence.connections = {}
        super(TestMemoryPersistence, self).setUp()

    def tearDown(self):
        # Clear all existing backends
        cinderlib.Backend.backends = {}
        cinderlib.Backend.global_initialization = False
        super(TestMemoryPersistence, self).tearDown()

    def sorted(self, resources):
        return sorted(resources, key=lambda x: x.id)

    def create_n_volumes(self, n):
        return self.create_volumes([{'size': i, 'name': 'disk%s' % i}
                                    for i in range(1, n+1)])

    def create_volumes(self, data):
        vols = []
        for d in data:
            d.setdefault('backend_or_vol', self.backend)
            vol = cinderlib.Volume(**d)
            vols.append(vol)
            self.persistence.set_volume(vol)
        return self.sorted(vols)

    def create_snapshots(self):
        vols = self.create_n_volumes(2)
        snaps = []
        for i, vol in enumerate(vols):
            snap = cinderlib.Snapshot(vol, name='snaps%s' % (i + i))
            snaps.append(snap)
            self.persistence.set_snapshot(snap)
        return self.sorted(snaps)

    def create_connections(self):
        vols = self.create_n_volumes(2)
        conns = []
        for i, vol in enumerate(vols):
            conn = cinderlib.Connection(self.backend, volume=vol)
            conns.append(conn)
            self.persistence.set_connection(conn)
        return self.sorted(conns)

    def test_db(self):
        self.assertIsInstance(self.persistence.db,
                              cinderlib.persistence.base.DB)

    def test_set_volume(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        self.assertDictEqual({}, self.persistence.volumes)

        self.persistence.set_volume(vol)
        self.assertDictEqual({vol.id: vol}, self.persistence.volumes)

    def test_get_volumes_all(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes()
        self.assertListEqual(vols, self.sorted(res))

    def test_get_volumes_by_id(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_id=vols[1].id)
        self.assertListEqual([vols[1]], res)

    def test_get_volumes_by_id_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_id='fake-uuid')
        self.assertListEqual([], res)

    def test_get_volumes_by_name_single(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_name=vols[1].name)
        self.assertListEqual([vols[1]], res)

    def test_get_volumes_by_name_multiple(self):
        volume_name = 'disk'
        vols = self.create_volumes([{'size': 1, 'name': volume_name},
                                    {'size': 2, 'name': volume_name}])
        res = self.persistence.get_volumes(volume_name=volume_name)
        self.assertListEqual(vols, self.sorted(res))

    def test_get_volumes_by_name_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_name='disk3')
        self.assertListEqual([], res)

    def test_get_volumes_by_backend(self):
        vols = self.create_n_volumes(2)
        backend2 = utils.FakeBackend(volume_backend_name='fake2')
        vol = self.create_volumes([{'backend_or_vol': backend2, 'size': 3}])

        res = self.persistence.get_volumes(backend_name=self.backend.id)
        self.assertListEqual(vols, self.sorted(res))

        res = self.persistence.get_volumes(backend_name=backend2.id)
        self.assertListEqual(vol, res)

    def test_get_volumes_by_backend_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(backend_name='fake2')
        self.assertListEqual([], res)

    def test_get_volumes_by_multiple(self):
        volume_name = 'disk'
        vols = self.create_volumes([{'size': 1, 'name': volume_name},
                                    {'size': 2, 'name': volume_name}])
        res = self.persistence.get_volumes(backend_name=self.backend.id,
                                           volume_name=volume_name,
                                           volume_id=vols[0].id)
        self.assertListEqual([vols[0]], res)

    def test_get_volumes_by_multiple_not_found(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(backend_name=self.backend.id,
                                           volume_name=vols[1].name,
                                           volume_id=vols[0].id)
        self.assertListEqual([], res)

    def test_set_snapshot(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        snap = cinderlib.Snapshot(vol, name='disk')

        self.assertDictEqual({}, self.persistence.snapshots)

        self.persistence.set_snapshot(snap)
        self.assertDictEqual({snap.id: snap}, self.persistence.snapshots)

    def get_snapshots_all(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots()
        self.assertListEqual(snaps, self.sorted(res))

    def test_get_snapshots_by_id(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_id=snaps[1].id)
        self.assertListEqual([snaps[1]], res)

    def test_get_snapshots_by_id_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_id='fake-uuid')
        self.assertListEqual([], res)

    def test_get_snapshots_by_name_single(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name=snaps[1].name)
        self.assertListEqual([snaps[1]], res)

    def test_get_snapshots_by_name_multiple(self):
        snap_name = 'snap'
        vol = self.create_volumes([{'size': 1}])[0]
        snaps = [cinderlib.Snapshot(vol, name=snap_name) for i in range(2)]
        [self.persistence.set_snapshot(snap) for snap in snaps]
        res = self.persistence.get_snapshots(snapshot_name=snap_name)
        self.assertListEqual(self.sorted(snaps), self.sorted(res))

    def test_get_snapshots_by_name_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name='snap3')
        self.assertListEqual([], res)

    def test_get_snapshots_by_volume(self):
        snaps = self.create_snapshots()
        vol = snaps[0].volume
        expected_snaps = [snaps[0], cinderlib.Snapshot(vol)]
        self.persistence.set_snapshot(expected_snaps[1])
        res = self.persistence.get_snapshots(volume_id=vol.id)
        self.assertListEqual(self.sorted(expected_snaps), self.sorted(res))

    def test_get_snapshots_by_volume_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(volume_id='fake_uuid')
        self.assertListEqual([], res)

    def test_get_snapshots_by_multiple(self):
        snap_name = 'snap'
        vol = self.create_volumes([{'size': 1}])[0]
        snaps = [cinderlib.Snapshot(vol, name=snap_name) for i in range(2)]
        [self.persistence.set_snapshot(snap) for snap in snaps]
        res = self.persistence.get_snapshots(volume_id=vol.id,
                                             snapshot_name=snap_name,
                                             snapshot_id=snaps[0].id)
        self.assertListEqual([snaps[0]], self.sorted(res))

    def test_get_snapshots_by_multiple_not_found(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name=snaps[1].name,
                                             volume_id=snaps[0].volume.id)
        self.assertListEqual([], res)

    def test_set_connection(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        conn = cinderlib.Connection(self.backend, volume=vol, connector={})

        self.assertDictEqual({}, self.persistence.connections)

        self.persistence.set_connection(conn)
        self.assertDictEqual({conn.id: conn}, self.persistence.connections)

    def get_connections_all(self):
        conns = self.create_connections()
        res = self.persistence.get_connections()
        self.assertListEqual(conns, self.sorted(res))

    def test_get_connections_by_id(self):
        conns = self.create_connections()
        res = self.persistence.get_connections(connection_id=conns[1].id)
        self.assertListEqual([conns[1]], res)

    def test_get_connections_by_id_not_found(self):
        self.create_connections()
        res = self.persistence.get_connections(connection_id='fake-uuid')
        self.assertListEqual([], res)

    def test_get_connections_by_volume(self):
        conns = self.create_connections()
        vol = conns[0].volume
        expected_conns = [conns[0], cinderlib.Connection(self.backend,
                                                         volume=vol)]
        self.persistence.set_connection(expected_conns[1])
        res = self.persistence.get_connections(volume_id=vol.id)
        self.assertListEqual(self.sorted(expected_conns), self.sorted(res))

    def test_get_connections_by_volume_not_found(self):
        self.create_connections()
        res = self.persistence.get_connections(volume_id='fake_uuid')
        self.assertListEqual([], res)

    def test_get_connections_by_multiple(self):
        vol = self.create_volumes([{'size': 1}])[0]
        conns = [cinderlib.Connection(self.backend, volume=vol)
                 for i in range(2)]
        [self.persistence.set_connection(conn) for conn in conns]
        res = self.persistence.get_connections(volume_id=vol.id,
                                               connection_id=conns[0].id)
        self.assertListEqual([conns[0]], self.sorted(res))

    def test_get_connections_by_multiple_not_found(self):
        conns = self.create_connections()
        res = self.persistence.get_connections(volume_id=conns[0].volume.id,
                                               connection_id=conns[1].id)
        self.assertListEqual([], res)
