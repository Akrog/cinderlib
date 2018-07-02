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
import inspect

from cinder.cmd import volume as volume_cmd
import six
from stevedore import driver

from cinderlib import exception
from cinderlib.persistence import base


DEFAULT_STORAGE = 'memory'


class MyDict(dict):
    """Custom non clearable dictionary.

    Required to overcome the nature of oslo.config where configuration comes
    from files and command line input.

    Using this dictionary we can load from memory everything and it won't clear
    things when we dynamically load a driver and the driver has new
    configuration options.
    """
    def clear(self):
        pass


def setup(config):
    """Setup persistence to be used in cinderlib.

    By default memory persistance will be used, but there are other mechanisms
    available and other ways to use custom mechanisms:

    - Persistence plugins: Plugin mechanism uses Python entrypoints under
      namespace cinderlib.persistence.storage, and cinderlib comes with 3
      different mechanisms, "memory", "dbms", and "memory_dbms".  To use any of
      these one must pass the string name in the storage parameter and any
      other configuration as keyword arguments.
    - Passing a class that inherits from PersistenceDriverBase as storage
      parameter and initialization parameters as keyword arguments.
    - Passing an instance that inherits from PersistenceDriverBase as storage
      parameter.
    """
    if config is None:
        config = {}
    else:
        config = config.copy()

    # Prevent driver dynamic loading clearing configuration options
    volume_cmd.CONF._ConfigOpts__cache = MyDict()

    # Default configuration is using memory storage
    storage = config.pop('storage', None) or DEFAULT_STORAGE
    if isinstance(storage, base.PersistenceDriverBase):
        return storage

    if inspect.isclass(storage) and issubclass(storage,
                                               base.PersistenceDriverBase):
            return storage(**config)

    if not isinstance(storage, six.string_types):
        raise exception.InvalidPersistence(storage)

    persistence_driver = driver.DriverManager(
        namespace='cinderlib.persistence.storage',
        name=storage,
        invoke_on_load=True,
        invoke_kwds=config,
    )
    return persistence_driver.driver
