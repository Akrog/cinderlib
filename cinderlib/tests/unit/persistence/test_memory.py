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

import cinderlib
from cinderlib.tests.unit.persistence import base


class TestMemoryPersistence(base.BasePersistenceTest):
    PERSISTENCE_CFG = {'storage': 'memory'}

    def tearDown(self):
        # Since this plugin uses class attributes we have to clear them
        self.persistence.volumes = {}
        self.persistence.snapshots = {}
        self.persistence.connections = {}
        self.persistence.key_values = {}
        super(TestMemoryPersistence, self).tearDown()

    def test_db(self):
        self.assertIsInstance(self.persistence.db,
                              cinderlib.persistence.base.DB)

    def test_set_volume(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        self.assertDictEqual({}, self.persistence.volumes)

        self.persistence.set_volume(vol)
        self.assertDictEqual({vol.id: vol}, self.persistence.volumes)

    def test_set_snapshot(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        snap = cinderlib.Snapshot(vol, name='disk')

        self.assertDictEqual({}, self.persistence.snapshots)

        self.persistence.set_snapshot(snap)
        self.assertDictEqual({snap.id: snap}, self.persistence.snapshots)

    def test_set_connection(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        conn = cinderlib.Connection(self.backend, volume=vol, connector={},
                                    connection_info={'conn': {'data': {}}})

        self.assertDictEqual({}, self.persistence.connections)

        self.persistence.set_connection(conn)
        self.assertDictEqual({conn.id: conn}, self.persistence.connections)

    def test_set_key_values(self):
        self.assertDictEqual({}, self.persistence.key_values)
        expected = [cinderlib.KeyValue('key', 'value')]
        self.persistence.set_key_value(expected[0])
        self.assertTrue('key' in self.persistence.key_values)
        self.assertEqual(expected, list(self.persistence.key_values.values()))
