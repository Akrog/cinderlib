====================
Metadata Persistence
====================

*Cinder* drivers are not stateless, and the interface between the *Cinder* core
code and the drivers allows them to return data that can be stored in the
database.  Some drivers, that have not been updated, are even accessing the
database directly.

Because *cinderlib* uses the *Cinder* drivers as they are, it cannot be
stateless either.

Originally *cinderlib* stored all the required metadata in RAM, and passed the
responsibility of persisting this information to the user of the library.

Library users would create or modify resources using *cinderlib*, and then
serialize the resources and manage the storage of this information themselves.
This allowed referencing those resources after exiting the application and in
case of a crash.

This solution would result in code duplication across projects, as many library
users would end up using the same storage types for the serialized data.
That's when the metadata persistence plugin was introduced in the code.

With the metadata plugin mechanism we can have plugins for different storages
and they can be shared between different projects.

*Cinderlib* includes 2 types of plugins providing 3 different persistence
solutions:

- Memory (the default)
- Database
- Database in memory

Using the memory mechanisms users can still use the JSON serialization
mechanism to store the medatada.

Currently we have memory and database plugins.  Users can store the data
wherever they want using the JSON serialization mechanism or with a custom
metadata plugin.

Persistence mechanism must be configured before initializing any *Backend*
using the `persistence_config` parameter in the `setup` or `global_setup`
methods.

.. note:: When deserializing data using the `load` method on memory based
   storage we will not be making this data available using the *Backend* unless
   we pass `save=True` on the `load` call.


Memory plugin
-------------

The memory plugin is the fastest one, but it's has its drawbacks.  It doesn't
provide persistence across application restarts and it's more likely to have
issues than the database plugin.

Even though it's more likely to present issues with some untested drivers, it
is still the default plugin, because it's the plugin that exposes the raw
plugin mechanism and will expose any incompatibility issues with external
plugins in *Cinder* drivers.

This plugin is identified with the name `memory`, and here we can see a simple
example of how to save everything to the database:

.. code-block:: python

   import cinderlib as cl

   cl.setup(persistence_config={'storage': 'memory'})

   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')
   vol = lvm.create_volume(1)

   with open('lvm.txt', 'w') as f:
       f.write(lvm.dumps)

And how to load it back:

.. code-block:: python

   import cinderlib as cl

   cl.setup(persistence_config={'storage': 'memory'})

   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')

   with open('cinderlib.txt', 'r') as f:
       data = f.read()
   backends = cl.load(data, save=True)
   print backends[0].volumes


Database plugin
---------------

This metadata plugin is the most likely to be compatible with any *Cinder*
driver, as its built on top of *Cinder's* actual database layer.

This plugin includes 2 storage options: memory and real database.  They are
identified with the storage identifiers `memory_db` and `db` respectively.

The memory option will store the data as an in memory SQLite database.  This
option helps debugging issues on untested drivers.  If a driver works with the
memory database plugin, but doesn't with the `memory` one, then the issue is
most likely caused by the driver accessing the database.  Accessing the
database could be happening directly importing the database layer, or
indirectly using versioned objects.

The memory database doesn't require any additional configuration, but when
using a real database we must pass the connection information using `SQLAlchemy
database URLs format`_ as the value of the `connection` key.

.. code-block:: python

   import cinderlib as cl

   persistence_config = {'storage': 'db', 'connection': 'sqlite:///cl.sqlite'}
   cl.setup(persistence_config=persistence_config)

   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')
   vol = lvm.create_volume(1)

Using it later is exactly the same:

.. code-block:: python

   import cinderlib as cl

   persistence_config = {'storage': 'db', 'connection': 'sqlite:///cl.sqlite'}
   cl.setup(persistence_config=persistence_config)

   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')

   print lvm.volumes


Custom plugins
--------------

The plugin mechanism uses Python entrypoints to identify plugins present in the
system.  So any module exposing the `cinderlib.persistence.storage` entrypoint
will be recognized as a *cinderlib* metadata persistence plugin.

As an example, the definition in `setup.py` of the entrypoints for the plugins
included in *cinderlib* is:

.. code-block:: python

   entry_points={
       'cinderlib.persistence.storage': [
           'memory = cinderlib.persistence.memory:MemoryPersistence',
           'db = cinderlib.persistence.dbms:DBPersistence',
           'memory_db = cinderlib.persistence.dbms:MemoryDBPersistence',
       ],
   },

But there may be cases were we don't want to create entry points available
system wide, and we want an application only plugin mechanism.  For this
purpose *cinderlib* supports passing a plugin instance or class as the value of
the `storage` key in the `persistence_config` parameters.

The instance and class must inherit from the `PersistenceDriverBase` in
`cinderlib/persistence/base.py` and implement all the following methods:

- `db`
- `get_volumes`
- `get_snapshots`
- `get_connections`
- `get_key_values`
- `set_volume`
- `set_snapshot`
- `set_connection`
- `set_key_value`
- `delete_volume`
- `delete_snapshot`
- `delete_connection`
- `delete_key_value`

And the `__init__` method is usually needed as well, and it will receive as
keyword arguments the parameters provided in the `persistence_config`.  The
`storage` key-value pair is not included as part of the keyword parameters.

The invocation with a class plugin would look something like this:


.. code-block:: python

   import cinderlib as cl
   from cinderlib.persistence import base

   class MyPlugin(base.PersistenceDriverBase):
       def __init__(self, location, user, password):
           ...

   persistence_config = {'storage': MyPlugin, 'location': '127.0.0.1',
                         'user': 'admin', 'password': 'nomoresecrets'}
   cl.setup(persistence_config=persistence_config)

   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')


Migrating storage
-----------------

Metadata is crucial for the proper operation of *cinderlib*, as the *Cinder*
drivers cannot retrieve this information from the storage backend.

There may be cases where we want to stop using a metadata plugin and start
using another one, but we have metadata on the old plugin, so we need to
migrate this information from one backend to another.

To achieve a metadata migration we can use methods `refresh`, `dump`, `load`,
and `set_persistence`.

An example code of how to migrate from SQLite to MySQL could look like this:

.. code-block:: python

   import cinderlib as cl

   # Setup the source persistence plugin
   persistence_config = {'storage': 'db',
                         'connection': 'sqlite:///cinderlib.sqlite'}
   cl.setup(persistence_config=persistence_config)

   # Setup backends we want to migrate
   lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                    volume_group='cinder-volumes',
                    target_protocol='iscsi',
                    target_helper='lioadm',
                    volume_backend_name='lvm_iscsi')

   # Get all the data into memory
   data = cl.dump()

   # Setup new persistence plugin
   new_config = {
       'storage': 'db',
       'connection': 'mysql+pymysql://user:password@IP/cinder?charset=utf8'
   }
   cl.Backend.set_persistence(new_config)

   # Load and save the data into the new plugin
   backends = cl.load(data, save=True)


.. _SQLAlchemy database URLs format: http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls
