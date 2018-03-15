from __future__ import absolute_import
import cinderlib.cinderlib as clib
from cinderlib.cinderlib import *  # noqa
from cinderlib import serialization
from cinderlib import objects

__author__ = """Gorka Eguileor"""
__email__ = 'geguileo@redhat.com'
__version__ = '0.1.0'
__all__ = clib.__all__

DEFAULT_PROJECT_ID = objects.DEFAULT_PROJECT_ID
DEFAULT_USER_ID = objects.DEFAULT_USER_ID
Volume = objects.Volume
Snapshot = objects.Snapshot
Connection = objects.Connection

load = serialization.load
json = serialization.json
jsons = serialization.jsons
