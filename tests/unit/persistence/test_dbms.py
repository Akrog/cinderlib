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

import tempfile
import unittest2

from cinder.cmd import volume as volume_cmd
from cinder.db.sqlalchemy import api as sqla_api
from cinder import objects as cinder_ovos
from oslo_db import api as oslo_db_api
from oslo_versionedobjects import fields

import cinderlib
from tests.unit import utils


class TestMemoryDBPersistence(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.original_impl = volume_cmd.session.IMPL
        # We check the entrypoint is working
        cinderlib.setup(persistence_config={'storage': 'memory_db'})
        cls.persistence = cinderlib.Backend.persistence
        cls.context = cinderlib.objects.CONTEXT

    @classmethod
    def tearDownClass(cls):
        volume_cmd.session.IMPL = cls.original_impl
        cinderlib.Backend.global_initialization = False

    def setUp(self):
        self.backend = utils.FakeBackend()

    def tearDown(self):
        # Clear all existing backends
        cinderlib.Backend.backends = {}
        sqla_api.model_query(self.context, sqla_api.models.Snapshot).delete()
        sqla_api.model_query(self.context,
                             sqla_api.models.VolumeAttachment).delete()
        sqla_api.model_query(self.context,
                             sqla_api.models.Volume).delete()
        super(TestMemoryDBPersistence, self).tearDown()

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

    def _convert_to_dict(self, obj):
        if not isinstance(obj, cinderlib.objects.Object):
            return obj

        res = dict(obj._ovo)
        for key, value in obj._ovo.fields.items():
            if isinstance(value, fields.ObjectField):
                res.pop(key, None)
        res.pop('glance_metadata', None)
        res.pop('metadata', None)
        return res

    def assertListEqualObj(self, expected, actual):
        exp = [self._convert_to_dict(e) for e in expected]
        act = [self._convert_to_dict(a) for a in actual]
        self.assertListEqual(exp, act)

    def assertEqualObj(self, expected, actual):
        exp = self._convert_to_dict(expected)
        act = self._convert_to_dict(actual)
        self.assertDictEqual(exp, act)

    def test_db(self):
        self.assertIsInstance(self.persistence.db,
                              oslo_db_api.DBAPI)

    def test_set_volume(self):
        res = sqla_api.volume_get_all(self.context)
        self.assertListEqual([], res)

        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        expected = {'availability_zone': vol.availability_zone,
                    'size': vol.size, 'name': vol.name}

        self.persistence.set_volume(vol)

        db_vol = sqla_api.volume_get(self.context, vol.id)
        actual = {'availability_zone': db_vol.availability_zone,
                  'size': db_vol.size, 'name': db_vol.display_name}

        self.assertDictEqual(expected, actual)

    def test_get_volumes_all(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes()
        self.assertListEqualObj(vols, self.sorted(res))

    def test_get_volumes_by_id(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_id=vols[1].id)
        # Use res instead of res[0] in case res is empty list
        self.assertListEqualObj([vols[1]], res)

    def test_get_volumes_by_id_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_id='fake-uuid')
        self.assertListEqualObj([], res)

    def test_get_volumes_by_name_single(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_name=vols[1].name)
        self.assertListEqualObj([vols[1]], res)

    def test_get_volumes_by_name_multiple(self):
        volume_name = 'disk'
        vols = self.create_volumes([{'size': 1, 'name': volume_name},
                                    {'size': 2, 'name': volume_name}])
        res = self.persistence.get_volumes(volume_name=volume_name)
        self.assertListEqualObj(vols, self.sorted(res))

    def test_get_volumes_by_name_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(volume_name='disk3')
        self.assertListEqualObj([], res)

    def test_get_volumes_by_backend(self):
        vols = self.create_n_volumes(2)
        backend2 = utils.FakeBackend(volume_backend_name='fake2')
        vol = self.create_volumes([{'backend_or_vol': backend2, 'size': 3}])

        res = self.persistence.get_volumes(backend_name=self.backend.id)
        self.assertListEqualObj(vols, self.sorted(res))

        res = self.persistence.get_volumes(backend_name=backend2.id)
        self.assertListEqualObj(vol, res)

    def test_get_volumes_by_backend_not_found(self):
        self.create_n_volumes(2)
        res = self.persistence.get_volumes(backend_name='fake2')
        self.assertListEqualObj([], res)

    def test_get_volumes_by_multiple(self):
        volume_name = 'disk'
        vols = self.create_volumes([{'size': 1, 'name': volume_name},
                                    {'size': 2, 'name': volume_name}])
        res = self.persistence.get_volumes(backend_name=self.backend.id,
                                           volume_name=volume_name,
                                           volume_id=vols[0].id)
        self.assertListEqualObj([vols[0]], res)

    def test_get_volumes_by_multiple_not_found(self):
        vols = self.create_n_volumes(2)
        res = self.persistence.get_volumes(backend_name=self.backend.id,
                                           volume_name=vols[1].name,
                                           volume_id=vols[0].id)
        self.assertListEqualObj([], res)

    def test_set_snapshot(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        snap = cinderlib.Snapshot(vol, name='disk')

        self.assertEqual(0, len(sqla_api.snapshot_get_all(self.context)))

        self.persistence.set_snapshot(snap)

        db_entries = sqla_api.snapshot_get_all(self.context)
        self.assertEqual(1, len(db_entries))

        ovo_snap = cinder_ovos.Snapshot(self.context)
        ovo_snap._from_db_object(ovo_snap._context, ovo_snap, db_entries[0])
        cl_snap = cinderlib.Snapshot(vol, __ovo=ovo_snap)

        self.assertEqualObj(snap, cl_snap)

    def get_snapshots_all(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots()
        self.assertListEqualObj(snaps, self.sorted(res))

    def test_get_snapshots_by_id(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_id=snaps[1].id)
        self.assertListEqualObj([snaps[1]], res)

    def test_get_snapshots_by_id_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_id='fake-uuid')
        self.assertListEqualObj([], res)

    def test_get_snapshots_by_name_single(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name=snaps[1].name)
        self.assertListEqualObj([snaps[1]], res)

    def test_get_snapshots_by_name_multiple(self):
        snap_name = 'snap'
        vol = self.create_volumes([{'size': 1}])[0]
        snaps = [cinderlib.Snapshot(vol, name=snap_name) for i in range(2)]
        [self.persistence.set_snapshot(snap) for snap in snaps]
        res = self.persistence.get_snapshots(snapshot_name=snap_name)
        self.assertListEqualObj(self.sorted(snaps), self.sorted(res))

    def test_get_snapshots_by_name_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name='snap3')
        self.assertListEqualObj([], res)

    def test_get_snapshots_by_volume(self):
        snaps = self.create_snapshots()
        vol = snaps[0].volume
        expected_snaps = [snaps[0], cinderlib.Snapshot(vol)]
        self.persistence.set_snapshot(expected_snaps[1])
        res = self.persistence.get_snapshots(volume_id=vol.id)
        self.assertListEqualObj(self.sorted(expected_snaps), self.sorted(res))

    def test_get_snapshots_by_volume_not_found(self):
        self.create_snapshots()
        res = self.persistence.get_snapshots(volume_id='fake_uuid')
        self.assertListEqualObj([], res)

    def test_get_snapshots_by_multiple(self):
        snap_name = 'snap'
        vol = self.create_volumes([{'size': 1}])[0]
        snaps = [cinderlib.Snapshot(vol, name=snap_name) for i in range(2)]
        [self.persistence.set_snapshot(snap) for snap in snaps]
        res = self.persistence.get_snapshots(volume_id=vol.id,
                                             snapshot_name=snap_name,
                                             snapshot_id=snaps[0].id)
        self.assertListEqualObj([snaps[0]], self.sorted(res))

    def test_get_snapshots_by_multiple_not_found(self):
        snaps = self.create_snapshots()
        res = self.persistence.get_snapshots(snapshot_name=snaps[1].name,
                                             volume_id=snaps[0].volume.id)
        self.assertListEqualObj([], res)

    def test_set_connection(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        conn = cinderlib.Connection(self.backend, volume=vol, connector={})

        self.assertEqual(0,
                         len(sqla_api.volume_attachment_get_all(self.context)))

        self.persistence.set_connection(conn)

        db_entries = sqla_api.volume_attachment_get_all(self.context)
        self.assertEqual(1, len(db_entries))

        ovo_conn = cinder_ovos.VolumeAttachment(self.context)
        ovo_conn._from_db_object(ovo_conn._context, ovo_conn, db_entries[0])
        cl_conn = cinderlib.Connection(vol.backend, volume=vol, __ovo=ovo_conn)

        self.assertEqualObj(conn, cl_conn)

    def get_connections_all(self):
        conns = self.create_connections()
        res = self.persistence.get_connections()
        self.assertListEqual(conns, self.sorted(res))

    def test_get_connections_by_id(self):
        conns = self.create_connections()
        res = self.persistence.get_connections(connection_id=conns[1].id)
        self.assertListEqualObj([conns[1]], res)

    def test_get_connections_by_id_not_found(self):
        self.create_connections()
        res = self.persistence.get_connections(connection_id='fake-uuid')
        self.assertListEqualObj([], res)

    def test_get_connections_by_volume(self):
        conns = self.create_connections()
        vol = conns[0].volume
        expected_conns = [conns[0], cinderlib.Connection(self.backend,
                                                         volume=vol)]
        self.persistence.set_connection(expected_conns[1])
        res = self.persistence.get_connections(volume_id=vol.id)
        self.assertListEqualObj(self.sorted(expected_conns), self.sorted(res))

    def test_get_connections_by_volume_not_found(self):
        self.create_connections()
        res = self.persistence.get_connections(volume_id='fake_uuid')
        self.assertListEqualObj([], res)

    def test_get_connections_by_multiple(self):
        vol = self.create_volumes([{'size': 1}])[0]
        conns = [cinderlib.Connection(self.backend, volume=vol)
                 for i in range(2)]
        [self.persistence.set_connection(conn) for conn in conns]
        res = self.persistence.get_connections(volume_id=vol.id,
                                               connection_id=conns[0].id)
        self.assertListEqualObj([conns[0]], self.sorted(res))

    def test_get_connections_by_multiple_not_found(self):
        conns = self.create_connections()
        res = self.persistence.get_connections(volume_id=conns[0].volume.id,
                                               connection_id=conns[1].id)
        self.assertListEqualObj([], res)


class TestDBPersistence(TestMemoryDBPersistence):

    @classmethod
    def setUpClass(cls):
        cls.original_impl = volume_cmd.session.IMPL
        # Some Windows systems won't let us open the file a second time
        cls.db_file = tempfile.NamedTemporaryFile()
        connection = 'sqlite:///' + cls.db_file.name

        # We check the entrypoint is working
        cinderlib.setup(persistence_config={'storage': 'db',
                                            'connection': connection})
        cls.persistence = cinderlib.Backend.persistence
        cls.context = cinderlib.objects.CONTEXT

    @classmethod
    def tearDownClass(cls):
        volume_cmd.session.IMPL = cls.original_impl
        cinderlib.Backend.global_initialization = False
        # TODO(geguileo): Can't seem to be able to close the DB so the close
        # doesn't delete the file.
        sqla_api.get_engine().pool.dispose()
        sqla_api.dispose_engine()
        cls.db_file.close()
