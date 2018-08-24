from __future__ import absolute_import
from cinderlib import workarounds  # noqa
from cinderlib import cinderlib
from cinderlib import serialization
from cinderlib import objects

__author__ = """Gorka Eguileor"""
__email__ = 'geguileo@redhat.com'
__version__ = '0.2.2'

DEFAULT_PROJECT_ID = objects.DEFAULT_PROJECT_ID
DEFAULT_USER_ID = objects.DEFAULT_USER_ID
Volume = objects.Volume
Snapshot = objects.Snapshot
Connection = objects.Connection
KeyValue = objects.KeyValue

load = serialization.load
json = serialization.json
jsons = serialization.jsons
dump = serialization.dump
dumps = serialization.dumps

setup = cinderlib.setup
Backend = cinderlib.Backend
