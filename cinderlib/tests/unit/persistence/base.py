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

from cinder.cmd import volume as volume_cmd
from cinder.db.sqlalchemy import api
from cinder.db.sqlalchemy import models
from oslo_versionedobjects import fields

import cinderlib
from cinderlib.tests.unit import base
from cinderlib.tests.unit import utils


class BasePersistenceTest(base.BaseTest):
    @classmethod
    def setUpClass(cls):
        cls.original_impl = volume_cmd.session.IMPL
        cinderlib.Backend.global_initialization = False
        cinderlib.setup(persistence_config=cls.PERSISTENCE_CFG)

    @classmethod
    def tearDownClass(cls):
        volume_cmd.session.IMPL = cls.original_impl
        cinderlib.Backend.global_initialization = False
        api.main_context_manager = api.enginefacade.transaction_context()

    def setUp(self):
        super(BasePersistenceTest, self).setUp()
        self.context = cinderlib.objects.CONTEXT

    def sorted(self, resources, key='id'):
        return sorted(resources, key=lambda x: getattr(x, key))

    def create_n_volumes(self, n):
        return self.create_volumes([{'size': i, 'name': 'disk%s' % i}
                                    for i in range(1, n + 1)])

    def create_volumes(self, data, sort=True):
        vols = []
        for d in data:
            d.setdefault('backend_or_vol', self.backend)
            vol = cinderlib.Volume(**d)
            vols.append(vol)
            self.persistence.set_volume(vol)
        if sort:
            return self.sorted(vols)
        return vols

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
            conn = cinderlib.Connection(self.backend, volume=vol,
                                        connection_info={'conn': {'data': {}}})
            conns.append(conn)
            self.persistence.set_connection(conn)
        return self.sorted(conns)

    def create_key_values(self):
        kvs = []
        for i in range(2):
            kv = cinderlib.KeyValue(key='key%i' % i, value='value%i' % i)
            kvs.append(kv)
            self.persistence.set_key_value(kv)
        return kvs

    def _convert_to_dict(self, obj):
        if isinstance(obj, models.BASE):
            return dict(obj)

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
        raise NotImplementedError('Test class must implement this method')

    def test_set_volume(self):
        raise NotImplementedError('Test class must implement this method')

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

    def _check_volume_type(self, extra_specs, qos_specs, vol):
        self.assertEqual(vol.id, vol.volume_type.id)
        self.assertEqual(vol.id, vol.volume_type.name)
        self.assertTrue(vol.volume_type.is_public)
        self.assertEqual(extra_specs, vol.volume_type.extra_specs)

        if qos_specs:
            self.assertEqual(vol.id, vol.volume_type.qos_specs_id)
            self.assertEqual(vol.id, vol.volume_type.qos_specs.id)
            self.assertEqual(vol.id, vol.volume_type.qos_specs.name)
            self.assertEqual('back-end', vol.volume_type.qos_specs.consumer)
            self.assertEqual(qos_specs, vol.volume_type.qos_specs.specs)
        else:
            self.assertIsNone(vol.volume_type.qos_specs_id)

    def test_get_volumes_extra_specs(self):
        extra_specs = [{'k1': 'v1', 'k2': 'v2'},
                       {'kk1': 'vv1', 'kk2': 'vv2', 'kk3': 'vv3'}]
        vols = self.create_volumes(
            [{'size': 1, 'extra_specs': extra_specs[0]},
             {'size': 2, 'extra_specs': extra_specs[1]}],
            sort=False)

        # Check the volume type and the extra specs on created volumes
        for i in range(len(vols)):
            self._check_volume_type(extra_specs[i], None, vols[i])

        # Check that we get what we stored
        res = self.persistence.get_volumes(backend_name=self.backend.id)
        vols = self.sorted(vols)
        self.assertListEqualObj(vols, self.sorted(res))
        for i in range(len(vols)):
            self._check_volume_type(vols[i].volume_type.extra_specs, {},
                                    vols[i])

    def test_get_volumes_qos_specs(self):
        qos_specs = [{'q1': 'r1', 'q2': 'r2'},
                     {'qq1': 'rr1', 'qq2': 'rr2', 'qq3': 'rr3'}]
        vols = self.create_volumes(
            [{'size': 1, 'qos_specs': qos_specs[0]},
             {'size': 2, 'qos_specs': qos_specs[1]}],
            sort=False)

        # Check the volume type and the extra specs on created volumes
        for i in range(len(vols)):
            self._check_volume_type({}, qos_specs[i], vols[i])

        # Check that we get what we stored
        res = self.persistence.get_volumes(backend_name=self.backend.id)
        vols = self.sorted(vols)
        res = self.sorted(res)
        self.assertListEqualObj(vols, res)
        for i in range(len(vols)):
            self._check_volume_type({}, vols[i].volume_type.qos_specs.specs,
                                    vols[i])

    def test_get_volumes_extra_and_qos_specs(self):
        qos_specs = [{'q1': 'r1', 'q2': 'r2'},
                     {'qq1': 'rr1', 'qq2': 'rr2', 'qq3': 'rr3'}]
        extra_specs = [{'k1': 'v1', 'k2': 'v2'},
                       {'kk1': 'vv1', 'kk2': 'vv2', 'kk3': 'vv3'}]
        vols = self.create_volumes(
            [{'size': 1, 'qos_specs': qos_specs[0],
              'extra_specs': extra_specs[0]},
             {'size': 2, 'qos_specs': qos_specs[1],
              'extra_specs': extra_specs[1]}],
            sort=False)

        # Check the volume type and the extra specs on created volumes
        for i in range(len(vols)):
            self._check_volume_type(extra_specs[i], qos_specs[i], vols[i])

        # Check that we get what we stored
        res = self.persistence.get_volumes(backend_name=self.backend.id)
        vols = self.sorted(vols)
        self.assertListEqualObj(vols, self.sorted(res))
        for i in range(len(vols)):
            self._check_volume_type(vols[i].volume_type.extra_specs,
                                    vols[i].volume_type.qos_specs.specs,
                                    vols[i])

    def test_delete_volume(self):
        vols = self.create_n_volumes(2)
        self.persistence.delete_volume(vols[0])
        res = self.persistence.get_volumes()
        self.assertListEqualObj([vols[1]], res)

    def test_delete_volume_not_found(self):
        vols = self.create_n_volumes(2)
        fake_vol = cinderlib.Volume(backend_or_vol=self.backend)
        self.persistence.delete_volume(fake_vol)
        res = self.persistence.get_volumes()
        self.assertListEqualObj(vols, self.sorted(res))

    def test_set_snapshot(self):
        raise NotImplementedError('Test class must implement this method')

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

    def test_delete_snapshot(self):
        snaps = self.create_snapshots()
        self.persistence.delete_snapshot(snaps[0])
        res = self.persistence.get_snapshots()
        self.assertListEqualObj([snaps[1]], res)

    def test_delete_snapshot_not_found(self):
        snaps = self.create_snapshots()
        fake_snap = cinderlib.Snapshot(snaps[0].volume)
        self.persistence.delete_snapshot(fake_snap)
        res = self.persistence.get_snapshots()
        self.assertListEqualObj(snaps, self.sorted(res))

    def test_set_connection(self):
        raise NotImplementedError('Test class must implement this method')

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
        expected_conns = [conns[0], cinderlib.Connection(
            self.backend, volume=vol, connection_info={'conn': {'data': {}}})]
        self.persistence.set_connection(expected_conns[1])
        res = self.persistence.get_connections(volume_id=vol.id)
        self.assertListEqualObj(self.sorted(expected_conns), self.sorted(res))

    def test_get_connections_by_volume_not_found(self):
        self.create_connections()
        res = self.persistence.get_connections(volume_id='fake_uuid')
        self.assertListEqualObj([], res)

    def test_get_connections_by_multiple(self):
        vol = self.create_volumes([{'size': 1}])[0]
        conns = [cinderlib.Connection(self.backend, volume=vol,
                                      connection_info={'conn': {'data': {}}})
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

    def test_delete_connection(self):
        conns = self.create_connections()
        self.persistence.delete_connection(conns[1])
        res = self.persistence.get_connections()
        self.assertListEqualObj([conns[0]], res)

    def test_delete_connection_not_found(self):
        conns = self.create_connections()
        fake_conn = cinderlib.Connection(
            self.backend,
            volume=conns[0].volume,
            connection_info={'conn': {'data': {}}})
        self.persistence.delete_connection(fake_conn)
        res = self.persistence.get_connections()
        self.assertListEqualObj(conns, self.sorted(res))

    def test_set_key_values(self):
        raise NotImplementedError('Test class must implement this method')

    def assertKVsEqual(self, expected, actual):
        if len(expected) == len(actual):
            for (key, value), actual in zip(expected, actual):
                self.assertEqual(key, actual.key)
                self.assertEqual(value, actual.value)
            return
        assert False, '%s is not equal to %s' % (expected, actual)

    def get_key_values_all(self):
        kvs = self.create_key_values()
        res = self.persistence.get_key_values()
        self.assertListEqual(kvs, self.sorted(res, 'key'))

    def test_get_key_values_by_key(self):
        kvs = self.create_key_values()
        res = self.persistence.get_key_values(key=kvs[1].key)
        self.assertListEqual([kvs[1]], res)

    def test_get_key_values_by_key_not_found(self):
        self.create_key_values()
        res = self.persistence.get_key_values(key='fake-uuid')
        self.assertListEqual([], res)

    def test_delete_key_value(self):
        kvs = self.create_key_values()
        self.persistence.delete_key_value(kvs[1])
        res = self.persistence.get_key_values()
        self.assertListEqual([kvs[0]], res)

    def test_delete_key_not_found(self):
        kvs = self.create_key_values()
        fake_key = cinderlib.KeyValue('fake-key')
        self.persistence.delete_key_value(fake_key)
        res = self.persistence.get_key_values()
        self.assertListEqual(kvs, self.sorted(res, 'key'))
