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

from cinder.db import api as db_api
from cinder.db import migration
from cinder.db.sqlalchemy import api as sqla_api
from cinder.db.sqlalchemy import models
from cinder import objects as cinder_objs
from oslo_config import cfg
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
    GET_METHODS_PER_DB_MODEL = {
        cinder_objs.VolumeType.model: 'volume_type_get',
        cinder_objs.QualityOfServiceSpecs.model: 'qos_specs_get',
    }

    def __init__(self, connection, sqlite_synchronous=True,
                 soft_deletes=False):
        self.soft_deletes = soft_deletes
        cfg.CONF.set_override('connection', connection, 'database')
        cfg.CONF.set_override('sqlite_synchronous',
                              sqlite_synchronous,
                              'database')

        # Suppress logging for migration
        migrate_logger = logging.getLogger('migrate')
        migrate_logger.setLevel(logging.WARNING)

        self._clear_facade()
        self.db_instance = db_api.oslo_db_api.DBAPI.from_config(
            conf=cfg.CONF, backend_mapping=db_api._BACKEND_MAPPING,
            lazy=True)

        # We need to wrap some get methods that get called before the volume is
        # actually created.
        self.original_vol_type_get = self.db_instance.volume_type_get
        self.db_instance.volume_type_get = self.vol_type_get
        self.original_qos_specs_get = self.db_instance.qos_specs_get
        self.db_instance.qos_specs_get = self.qos_specs_get
        self.original_get_by_id = self.db_instance.get_by_id
        self.db_instance.get_by_id = self.get_by_id

        migration.db_sync()
        self._create_key_value_table()
        super(DBPersistence, self).__init__()

    def vol_type_get(self, context, id, inactive=False,
                     expected_fields=None):
        if id not in objects.Backend._volumes_inflight:
            return self.original_vol_type_get(context, id, inactive)

        vol = objects.Backend._volumes_inflight[id]._ovo
        if not vol.volume_type_id:
            return None
        return persistence_base.vol_type_to_dict(vol.volume_type)

    def qos_specs_get(self, context, qos_specs_id, inactive=False):
        if qos_specs_id not in objects.Backend._volumes_inflight:
            return self.original_qos_specs_get(context, qos_specs_id, inactive)

        vol = objects.Backend._volumes_inflight[qos_specs_id]._ovo
        if not vol.volume_type_id:
            return None
        return persistence_base.vol_type_to_dict(vol.volume_type)['qos_specs']

    def get_by_id(self, context, model, id, *args, **kwargs):
        if model not in self.GET_METHODS_PER_DB_MODEL:
            return self.original_get_by_id(context, model, id, *args, **kwargs)
        method = getattr(self, self.GET_METHODS_PER_DB_MODEL[model])
        return method(context, id)

    def _clear_facade(self):
        # This is for Pike
        if hasattr(sqla_api, '_FACADE'):
            sqla_api._FACADE = None
        # This is for Queens and Rocky (untested)
        elif hasattr(sqla_api, 'configure'):
            sqla_api.configure(cfg.CONF)

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
        # Use the % wildcard to ignore the host name on the backend_name search
        host = '%@' + backend_name if backend_name else None
        filters = self._build_filter(id=volume_id, display_name=volume_name,
                                     host=host)
        LOG.debug('get_volumes for %s', filters)
        ovos = cinder_objs.VolumeList.get_all(objects.CONTEXT, filters=filters)
        result = []
        for ovo in ovos:
            backend = ovo.host.split('@')[-1].split('#')[0]

            # Trigger lazy loading of specs
            if ovo.volume_type_id:
                ovo.volume_type.extra_specs
                ovo.volume_type.qos_specs

            result.append(objects.Volume(backend, __ovo=ovo))

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

        extra_specs = changed.pop('extra_specs', None)
        qos_specs = changed.pop('qos_specs', None)

        # Since OVOs are not tracking QoS or Extra specs dictionary changes,
        # we only support setting QoS or Extra specs on creation or add them
        # later.
        if changed.get('volume_type_id'):
            vol_type_fields = {'id': volume.volume_type_id,
                               'name': volume.volume_type_id,
                               'extra_specs': extra_specs,
                               'is_public': True}
            if qos_specs:
                res = self.db.qos_specs_create(objects.CONTEXT,
                                               {'name': volume.volume_type_id,
                                                'consumer': 'back-end',
                                                'specs': qos_specs})
                # Cinder is automatically generating an ID, replace it
                query = sqla_api.model_query(objects.CONTEXT,
                                             models.QualityOfServiceSpecs)
                query.filter_by(id=res['id']).update(
                    {'id': volume.volume_type.qos_specs_id})

            self.db.volume_type_create(objects.CONTEXT, vol_type_fields)
        else:
            if extra_specs is not None:
                self.db.volume_type_extra_specs_update_or_create(
                    objects.CONTEXT, volume.volume_type_id, extra_specs)

                self.db.qos_specs_update(objects.CONTEXT,
                                         volume.volume_type.qos_specs_id,
                                         {'name': volume.volume_type_id,
                                          'consumer': 'back-end',
                                          'specs': qos_specs})

        # Create the volume
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
            if volume.volume_type_id:
                LOG.debug('soft deleting volume type %s',
                          volume.volume_type_id)
                self.db.volume_destroy(objects.CONTEXT, volume.volume_type_id)
                if volume.volume_type.qos_specs_id:
                    self.db.qos_specs_delete(objects.CONTEXT,
                                             volume.volume_type.qos_specs_id)
        else:
            LOG.debug('hard deleting volume %s', volume.id)
            query = sqla_api.model_query(objects.CONTEXT, models.Volume)
            query.filter_by(id=volume.id).delete()
            if volume.volume_type_id:
                LOG.debug('hard deleting volume type %s',
                          volume.volume_type_id)
                query = sqla_api.model_query(objects.CONTEXT,
                                             models.VolumeTypeExtraSpecs)
                query.filter_by(volume_type_id=volume.volume_type_id).delete()

                query = sqla_api.model_query(objects.CONTEXT,
                                             models.VolumeType)
                query.filter_by(id=volume.volume_type_id).delete()

                query = sqla_api.model_query(objects.CONTEXT,
                                             models.QualityOfServiceSpecs)
                qos_id = volume.volume_type.qos_specs_id
                if qos_id:
                    query.filter(sqla_api.or_(
                        models.QualityOfServiceSpecs.id == qos_id,
                        models.QualityOfServiceSpecs.specs_id == qos_id
                    )).delete()
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
