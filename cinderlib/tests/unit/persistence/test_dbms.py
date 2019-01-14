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

from cinder.db.sqlalchemy import api as sqla_api
from cinder import objects as cinder_ovos
from oslo_db import api as oslo_db_api

import cinderlib
from cinderlib.persistence import dbms
from cinderlib.tests.unit.persistence import base


class TestDBPersistence(base.BasePersistenceTest):
    CONNECTION = 'sqlite:///' + tempfile.NamedTemporaryFile().name
    PERSISTENCE_CFG = {'storage': 'db',
                       'connection': CONNECTION}

    def tearDown(self):
        sqla_api.model_query(self.context, sqla_api.models.Snapshot).delete()
        sqla_api.model_query(self.context,
                             sqla_api.models.VolumeAttachment).delete()
        sqla_api.model_query(self.context,
                             sqla_api.models.Volume).delete()
        sqla_api.get_session().query(dbms.KeyValue).delete()
        super(TestDBPersistence, self).tearDown()

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

    def test_set_connection(self):
        vol = cinderlib.Volume(self.backend, size=1, name='disk')
        conn = cinderlib.Connection(self.backend, volume=vol, connector={},
                                    connection_info={'conn': {'data': {}}})

        self.assertEqual(0,
                         len(sqla_api.volume_attachment_get_all(self.context)))

        self.persistence.set_connection(conn)

        db_entries = sqla_api.volume_attachment_get_all(self.context)
        self.assertEqual(1, len(db_entries))

        ovo_conn = cinder_ovos.VolumeAttachment(self.context)
        ovo_conn._from_db_object(ovo_conn._context, ovo_conn, db_entries[0])
        cl_conn = cinderlib.Connection(vol.backend, volume=vol, __ovo=ovo_conn)

        self.assertEqualObj(conn, cl_conn)

    def test_set_key_values(self):
        res = sqla_api.get_session().query(dbms.KeyValue).all()
        self.assertListEqual([], res)

        expected = [dbms.KeyValue(key='key', value='value')]
        self.persistence.set_key_value(expected[0])

        actual = sqla_api.get_session().query(dbms.KeyValue).all()
        self.assertListEqualObj(expected, actual)


class TestMemoryDBPersistence(TestDBPersistence):
    PERSISTENCE_CFG = {'storage': 'memory_db'}
