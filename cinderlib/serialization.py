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

"""Oslo Versioned Objects helper file.

These methods help with the serialization of Cinderlib objects that uses the
OVO serialization mechanism, so we remove circular references when doing the
JSON serialization of objects (for example in a Volume OVO it has a 'snapshot'
field which is a Snapshot OVO that has a 'volume' back reference), piggy back
on the OVO's serialization mechanism to add/get additional data we want.
"""

import functools
import json as json_lib
import six

from cinder.objects import base as cinder_base_ovo
from oslo_versionedobjects import base as base_ovo
from oslo_versionedobjects import fields as ovo_fields

from cinderlib import objects


# Variable used to avoid circular references
BACKEND_CLASS = None


def setup(backend_class):
    global BACKEND_CLASS
    BACKEND_CLASS = backend_class

    # Use custom dehydration methods that prevent maximum recursion errors
    # due to circular references:
    #   ie: snapshot -> volume -> snapshots -> snapshot
    base_ovo.VersionedObject.obj_to_primitive = obj_to_primitive
    cinder_base_ovo.CinderObject.obj_from_primitive = classmethod(
        obj_from_primitive)

    fields = base_ovo.obj_fields
    fields.Object.to_primitive = staticmethod(field_ovo_to_primitive)
    fields.Field.to_primitive = field_to_primitive
    fields.List.to_primitive = iterable_to_primitive
    fields.Set.to_primitive = iterable_to_primitive
    fields.Dict.to_primitive = dict_to_primitive
    wrap_to_primitive(fields.FieldType)
    wrap_to_primitive(fields.DateTime)
    wrap_to_primitive(fields.IPAddress)


def wrap_to_primitive(cls):
    method = getattr(cls, 'to_primitive')

    @functools.wraps(method)
    def to_primitive(obj, attr, value, visited=None):
        return method(obj, attr, value)
    setattr(cls, 'to_primitive', staticmethod(to_primitive))


def _set_visited(element, visited):
    # visited keeps track of elements visited to prevent loops
    if visited is None:
        visited = set()
    # We only care about complex object that can have loops, others are ignored
    # to prevent us from not serializing simple objects, such as booleans, that
    # can have the same instance used for multiple fields.
    if isinstance(element,
                  (ovo_fields.ObjectField, cinder_base_ovo.CinderObject)):
        visited.add(id(element))
    return visited


def obj_to_primitive(self, target_version=None,
                     version_manifest=None, visited=None):
    # No target_version, version_manifest, or changes support
    visited = _set_visited(self, visited)
    primitive = {}
    for name, field in self.fields.items():
        if self.obj_attr_is_set(name):
            value = getattr(self, name)
            # Skip cycles
            if id(value) in visited:
                continue
            primitive[name] = field.to_primitive(self, name, value,
                                                 visited)

    obj_name = self.obj_name()
    obj = {
        self._obj_primitive_key('name'): obj_name,
        self._obj_primitive_key('namespace'): self.OBJ_PROJECT_NAMESPACE,
        self._obj_primitive_key('version'): self.VERSION,
        self._obj_primitive_key('data'): primitive
    }

    # Piggyback to store our own data
    cl_obj = getattr(self, '_cl_obj', None)
    clib_data = cl_obj and cl_obj._to_primitive()
    if clib_data:
        obj['cinderlib.data'] = clib_data

    return obj


def obj_from_primitive(
        cls, primitive, context=None,
        original_method=cinder_base_ovo.CinderObject.obj_from_primitive):
    result = original_method(primitive, context)
    result.cinderlib_data = primitive.get('cinderlib.data')
    return result


def field_ovo_to_primitive(obj, attr, value, visited=None):
    return value.obj_to_primitive(visited=visited)


def field_to_primitive(self, obj, attr, value, visited=None):
    if value is None:
        return None
    return self._type.to_primitive(obj, attr, value, visited)


def iterable_to_primitive(self, obj, attr, value, visited=None):
    visited = _set_visited(self, visited)
    result = []
    for elem in value:
        if id(elem) in visited:
            continue
        _set_visited(elem, visited)
        r = self._element_type.to_primitive(obj, attr, elem, visited)
        result.append(r)
    return result


def dict_to_primitive(self, obj, attr, value, visited=None):
    visited = _set_visited(self, visited)
    primitive = {}
    for key, elem in value.items():
        if id(elem) in visited:
            continue
        _set_visited(elem, visited)
        primitive[key] = self._element_type.to_primitive(
            obj, '%s["%s"]' % (attr, key), elem, visited)
    return primitive


def load(json_src, save=False):
    """Load any json serialized cinderlib object."""
    if isinstance(json_src, six.string_types):
        json_src = json_lib.loads(json_src)

    if isinstance(json_src, list):
        return [getattr(objects, obj['class']).load(obj, save)
                for obj in json_src]

    return getattr(objects, json_src['class']).load(json_src, save)


def json():
    """Convert to Json everything we have in this system."""
    return [backend.json for backend in BACKEND_CLASS.backends.values()]


def jsons():
    """Convert to a Json string everything we have in this system."""
    return json_lib.dumps(json(), separators=(',', ':'))


def dump():
    """Convert to Json everything we have in this system."""
    return [backend.dump for backend in BACKEND_CLASS.backends.values()]


def dumps():
    """Convert to a Json string everything we have in this system."""
    return json_lib.dumps(dump(), separators=(',', ':'))
