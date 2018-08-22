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

from __future__ import absolute_import

import logging

from cinder.cmd import volume as volume_cmd
from cinder.db import api as db_api
from cinder.db import migration
from cinder.db.sqlalchemy import api as sqla_api
from cinder.db.sqlalchemy import models
from cinder import objects as cinder_objs
from oslo_db import exception
from oslo_log import log

from cinderlib import objects
from cinderlib.persistence import base as persistence_base


LOG = log.getLogger(__name__)


class KeyValue(models.BASE, models.models.ModelBase, objects.KeyValue):
    __tablename__ = 'cinderlib_persistence_key_value'
    key = models.Column(models.String(255), primary_key=True)
    value = models.Column(models.Text)


class DBPersistence(persistence_base.PersistenceDriverBase):
    def __init__(self, connection, sqlite_synchronous=True,
                 soft_deletes=False):
        self.soft_deletes = soft_deletes
        volume_cmd.CONF.set_override('connection', connection, 'database')
        volume_cmd.CONF.set_override('sqlite_synchronous',
                                     sqlite_synchronous,
                                     'database')

        # Suppress logging for migration
        migrate_logger = logging.getLogger('migrate')
        migrate_logger.setLevel(logging.WARNING)

        self._clear_facade()
        self.db_instance = db_api.oslo_db_api.DBAPI.from_config(
            conf=volume_cmd.CONF, backend_mapping=db_api._BACKEND_MAPPING,
            lazy=True)

        migration.db_sync()
        self._create_key_value_table()
        super(DBPersistence, self).__init__()

    def _clear_facade(self):
        # This is for Pike
        if hasattr(sqla_api, '_FACADE'):
            sqla_api._FACADE = None
        # This is for Queens and Rocky (untested)
        elif hasattr(sqla_api, 'configure'):
            sqla_api.configure(volume_cmd.CONF)

    def _create_key_value_table(self):
        models.BASE.metadata.create_all(sqla_api.get_engine(),
                                        tables=[KeyValue.__table__])

    @property
    def db(self):
        return self.db_instance

    @staticmethod
    def _build_filter(**kwargs):
        return {key: value for key, value in kwargs.items() if value}

    def get_volumes(self, volume_id=None, volume_name=None, backend_name=None):
        filters = self._build_filter(id=volume_id, display_name=volume_name,
                                     availability_zone=backend_name)
        LOG.debug('get_volumes for %s', filters)
        ovos = cinder_objs.VolumeList.get_all(objects.CONTEXT, filters=filters)
        result = [objects.Volume(ovo.availability_zone, __ovo=ovo)
                  for ovo in ovos.objects]
        return result

    def get_snapshots(self, snapshot_id=None, snapshot_name=None,
                      volume_id=None):
        filters = self._build_filter(id=snapshot_id, volume_id=volume_id,
                                     display_name=snapshot_name)
        LOG.debug('get_snapshots for %s', filters)
        ovos = cinder_objs.SnapshotList.get_all(objects.CONTEXT,
                                                filters=filters)
        result = [objects.Snapshot(None, __ovo=ovo) for ovo in ovos.objects]
        return result

    def get_connections(self, connection_id=None, volume_id=None):
        filters = self._build_filter(id=connection_id, volume_id=volume_id)
        LOG.debug('get_connections for %s', filters)
        ovos = cinder_objs.VolumeAttachmentList.get_all(objects.CONTEXT,
                                                        filters)
        # Leverage lazy loading of the volume and backend in Connection
        result = [objects.Connection(None, volume=None, __ovo=ovo)
                  for ovo in ovos.objects]
        return result

    def _get_kv(self, key=None, session=None):
        session = session or sqla_api.get_session()
        query = session.query(KeyValue)
        if key is not None:
            query = query.filter_by(key=key)
        res = query.all()
        # If we want to use the result as an ORM
        if session:
            return res
        return [objects.KeyValue(r.key, r.value) for r in res]

    def get_key_values(self, key=None):
        return self._get_kv(key)

    def set_volume(self, volume):
        changed = self.get_changed_fields(volume)
        if not changed:
            changed = self.get_fields(volume)

        # Create
        if 'id' in changed:
            LOG.debug('set_volume creating %s', changed)
            try:
                self.db.volume_create(objects.CONTEXT, changed)
                changed = None
            except exception.DBDuplicateEntry:
                del changed['id']

        if changed:
            LOG.debug('set_volume updating %s', changed)
            self.db.volume_update(objects.CONTEXT, volume.id, changed)
        super(DBPersistence, self).set_volume(volume)

    def set_snapshot(self, snapshot):
        changed = self.get_changed_fields(snapshot)
        if not changed:
            changed = self.get_fields(snapshot)

        # Create
        if 'id' in changed:
            LOG.debug('set_snapshot creating %s', changed)
            try:
                self.db.snapshot_create(objects.CONTEXT, changed)
                changed = None
            except exception.DBDuplicateEntry:
                del changed['id']

        if changed:
            LOG.debug('set_snapshot updating %s', changed)
            self.db.snapshot_update(objects.CONTEXT, snapshot.id, changed)
        super(DBPersistence, self).set_snapshot(snapshot)

    def set_connection(self, connection):
        changed = self.get_changed_fields(connection)
        if not changed:
            changed = self.get_fields(connection)

        if 'connection_info' in changed:
            connection._convert_connection_info_to_db_format(changed)

        if 'connector' in changed:
            connection._convert_connector_to_db_format(changed)

        # Create
        if 'id' in changed:
            LOG.debug('set_connection creating %s', changed)
            try:
                sqla_api.volume_attach(objects.CONTEXT, changed)
                changed = None
            except exception.DBDuplicateEntry:
                del changed['id']

        if changed:
            LOG.debug('set_connection updating %s', changed)
            self.db.volume_attachment_update(objects.CONTEXT, connection.id,
                                             changed)
        super(DBPersistence, self).set_connection(connection)

    def set_key_value(self, key_value):
        session = sqla_api.get_session()
        with session.begin():
            kv = self._get_kv(key_value.key, session)
            kv = kv[0] if kv else KeyValue(key=key_value.key)
            kv.value = key_value.value
            session.add(kv)

    def delete_volume(self, volume):
        if self.soft_deletes:
            LOG.debug('soft deleting volume %s', volume.id)
            self.db.volume_destroy(objects.CONTEXT, volume.id)
        else:
            LOG.debug('hard deleting volume %s', volume.id)
            query = sqla_api.model_query(objects.CONTEXT, models.Volume)
            query.filter_by(id=volume.id).delete()
        super(DBPersistence, self).delete_volume(volume)

    def delete_snapshot(self, snapshot):
        if self.soft_deletes:
            LOG.debug('soft deleting snapshot %s', snapshot.id)
            self.db.snapshot_destroy(objects.CONTEXT, snapshot.id)
        else:
            LOG.debug('hard deleting snapshot %s', snapshot.id)
            query = sqla_api.model_query(objects.CONTEXT, models.Snapshot)
            query.filter_by(id=snapshot.id).delete()
        super(DBPersistence, self).delete_snapshot(snapshot)

    def delete_connection(self, connection):
        if self.soft_deletes:
            LOG.debug('soft deleting connection %s', connection.id)
            self.db.attachment_destroy(objects.CONTEXT, connection.id)
        else:
            LOG.debug('hard deleting connection %s', connection.id)
            query = sqla_api.model_query(objects.CONTEXT,
                                         models.VolumeAttachment)
            query.filter_by(id=connection.id).delete()
        super(DBPersistence, self).delete_connection(connection)

    def delete_key_value(self, key_value):
        query = sqla_api.get_session().query(KeyValue)
        query.filter_by(key=key_value.key).delete()


class MemoryDBPersistence(DBPersistence):
    def __init__(self):
        super(MemoryDBPersistence, self).__init__(connection='sqlite://')
