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

# NOTE(geguileo): Probably a good idea not to depend on cinder.cmd.volume
# having all the other imports as they could change.
from cinder import objects
from cinder.objects import base as cinder_base_ovo
from oslo_utils import timeutils
from oslo_versionedobjects import fields
import six

import cinderlib
from cinderlib import serialization


class PersistenceDriverBase(object):
    """Provide Metadata Persistency for our resources.

    This class will be used to store new resources as they are created,
    updated, and removed, as well as provide a mechanism for users to retrieve
    volumes, snapshots, and connections.
    """
    def __init__(self, **kwargs):
        pass

    @property
    def db(self):
        raise NotImplementedError()

    def get_volumes(self, volume_id=None, volume_name=None, backend_name=None):
        raise NotImplementedError()

    def get_snapshots(self, snapshot_id=None, snapshot_name=None,
                      volume_id=None):
        raise NotImplementedError()

    def get_connections(self, connection_id=None, volume_id=None):
        raise NotImplementedError()

    def get_key_values(self, key):
        raise NotImplementedError()

    def set_volume(self, volume):
        self.reset_change_tracker(volume)
        if volume.volume_type:
            volume.volume_type.obj_reset_changes()
            if volume.volume_type.qos_specs_id:
                volume.volume_type.qos_specs.obj_reset_changes()

    def set_snapshot(self, snapshot):
        self.reset_change_tracker(snapshot)

    def set_connection(self, connection):
        self.reset_change_tracker(connection)

    def set_key_value(self, key_value):
        pass

    def delete_volume(self, volume):
        self._set_deleted(volume)
        self.reset_change_tracker(volume)

    def delete_snapshot(self, snapshot):
        self._set_deleted(snapshot)
        self.reset_change_tracker(snapshot)

    def delete_connection(self, connection):
        self._set_deleted(connection)
        self.reset_change_tracker(connection)

    def delete_key_value(self, key):
        pass

    def _set_deleted(self, resource):
        resource._ovo.deleted = True
        resource._ovo.deleted_at = timeutils.utcnow()
        if hasattr(resource._ovo, 'status'):
            resource._ovo.status = 'deleted'

    def reset_change_tracker(self, resource, fields=None):
        if isinstance(fields, six.string_types):
            fields = (fields,)
        resource._ovo.obj_reset_changes(fields)

    def get_changed_fields(self, resource):
        # NOTE(geguileo): We don't use cinder_obj_get_changes to prevent
        # recursion to children OVO which we are not interested and may result
        # in circular references.
        result = {key: getattr(resource._ovo, key)
                  for key in resource._changed_fields
                  if not isinstance(resource.fields[key], fields.ObjectField)}
        if getattr(resource._ovo, 'volume_type_id', None):
            if ('qos_specs' in resource.volume_type._changed_fields and
                    resource.volume_type.qos_specs):
                result['qos_specs'] = resource._ovo.volume_type.qos_specs.specs
            if ('extra_specs' in resource.volume_type._changed_fields and
                    resource.volume_type.extra_specs):
                result['extra_specs'] = resource._ovo.volume_type.extra_specs
        return result

    def get_fields(self, resource):
        result = {
            key: getattr(resource._ovo, key)
            for key in resource.fields
            if (resource._ovo.obj_attr_is_set(key) and
                key not in getattr(resource, 'obj_extra_fields', []) and not
                isinstance(resource.fields[key], fields.ObjectField))
        }
        if getattr(resource._ovo, 'volume_type_id', None):
            result['extra_specs'] = resource._ovo.volume_type.extra_specs
            if resource._ovo.volume_type.qos_specs_id:
                result['qos_specs'] = resource._ovo.volume_type.qos_specs.specs
        return result


class DB(object):
    """Replacement for DB access methods.

    This will serve as replacement for methods used by:

    - Drivers
    - OVOs' get_by_id and save methods
    - DB implementation

    Data will be retrieved using the persistence driver we setup.
    """
    GET_METHODS_PER_DB_MODEL = {
        objects.Volume.model: 'volume_get',
        objects.VolumeType.model: 'volume_type_get',
        objects.Snapshot.model: 'snapshot_get',
        objects.QualityOfServiceSpecs.model: 'qos_specs_get',
    }

    def __init__(self, persistence_driver):
        self.persistence = persistence_driver

        # Replace get_by_id OVO methods with something that will return
        # expected data
        objects.Volume.get_by_id = self.volume_get
        objects.Snapshot.get_by_id = self.snapshot_get

        # Disable saving in OVOs
        for ovo_name in cinder_base_ovo.CinderObjectRegistry.obj_classes():
            ovo_cls = getattr(objects, ovo_name)
            ovo_cls.save = lambda *args, **kwargs: None

    def volume_get(self, context, volume_id, *args, **kwargs):
        return self.persistence.get_volumes(volume_id)[0]._ovo

    def snapshot_get(self, context, snapshot_id, *args, **kwargs):
        return self.persistence.get_snapshots(snapshot_id)[0]._ovo

    def volume_type_get(self, context, id, inactive=False,
                        expected_fields=None):
        if id in cinderlib.Backend._volumes_inflight:
            vol = cinderlib.Backend._volumes_inflight[id]
        else:
            vol = self.persistence.get_volumes(id)[0]

        if not vol._ovo.volume_type_id:
            return None
        return vol_type_to_dict(vol._ovo.volume_type)

    def qos_specs_get(self, context, qos_specs_id, inactive=False):
        if qos_specs_id in cinderlib.Backend._volumes_inflight:
            vol = cinderlib.Backend._volumes_inflight[qos_specs_id]
        else:
            vol = self.persistence.get_volumes(qos_specs_id)[0]
        if not vol._ovo.volume_type_id:
            return None
        return vol_type_to_dict(vol._ovo.volume_type)['qos_specs']

    @classmethod
    def image_volume_cache_get_by_volume_id(cls, context, volume_id):
        return None

    def get_by_id(self, context, model, id, *args, **kwargs):
        method = getattr(self, self.GET_METHODS_PER_DB_MODEL[model])
        return method(context, id)


def vol_type_to_dict(volume_type):
    res = serialization.obj_to_primitive(volume_type)
    res = res['versioned_object.data']
    if res.get('qos_specs'):
        res['qos_specs'] = res['qos_specs']['versioned_object.data']
    return res
