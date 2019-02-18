=============
Serialization
=============

A *Cinder* driver is stateless on itself, but it still requires the right data
to work, and that's why the cinder-volume service takes care of storing the
state in the DB.  This means that *cinderlib* will have to simulate the DB for
the drivers, as some operations actually return additional data that needs to
be kept and provided in any future operation.

Originally *cinderlib* stored all the required metadata in RAM, and passed the
responsibility of persisting this information to the user of the library.

Library users would create or modify resources using *cinderlib*, and then
would have to serialize the resources and manage the storage of this
information.  This allowed referencing those resources after exiting the
application and in case of a crash.

Now we support :doc:`metadata` plugins, but there are still cases were we'll
want to serialize the data:

- When logging or debugging resources.
- When using a metadata plugin that stores the data in memory.
- Over the wire transmission of the connection information to attach a volume
  on a remote nodattach a volume on a remote node.

We have multiple methods to satisfy these needs, to serialize the data (`json`,
`jsons`, `dump`, `dumps`), to deserialize it (`load`), and to convert to a user
friendly object (`to_dict`).

To JSON
-------

We can get a JSON representation of any *cinderlib* object - *Backend*,
*Volume*, *Snapshot*, and *Connection* - using their following properties:

- `json`: Returns a JSON representation of the current object information as a
  Python dictionary.  Lazy loadable objects that have not been loaded will not
  be present in the resulting dictionary.

- `jsons`: Returns a string with the JSON representation.  It's the equivalent
  of converting to a string the dictionary from the `json` property.

- `dump`: Identical to the `json` property with the exception that it ensures
  all lazy loadable attributes have been loaded.  If an attribute had already
  been loaded its contents will not be refreshed.

- `dumps`: Returns a string with the JSON representation of the fully loaded
  object.  It's the equivalent of converting to a string the dictionary from
  the `dump` property.

Besides these resource specific properties, we also have their equivalent
methods at the library level that will operate on all the *Backends* present in
the application.

.. attention:: On the objects, these are properties (`volume.dumps`), but on
   the library, these are methods (`cinderlib.dumps()`).

.. note::

    We don't have to worry about circular references, such as a *Volume* with a
    *Snapshot* that has a reference to its source  *Volume*,  since *cinderlib*
    is prepared to handle them.

To demonstrate the serialization in *cinderlib* we can look at an easy way to
save all the *Backends'* resources information from an application that uses
*cinderlib* with the metadata stored in memory:

.. code-block:: python

    with open('cinderlib.txt', 'w') as f:
        f.write(cinderlib.dumps())

In a similar way we can also store a single *Backend* or a single *Volume*:

.. code-block:: python

    vol = lvm.create_volume(size=1)

    with open('lvm.txt', 'w') as f:
        f.write(lvm.dumps)

    with open('vol.txt', 'w') as f:
        f.write(vol.dumps)

We must remember that `dump` and `dumps` triggers loading of properties that
are not already loaded.  Any lazy loadable property that was already loaded
will not be updated.  A good way to ensure we are using the latest data is to
trigger a `refresh` on the backends before doing the `dump` or `dumps`.

.. code-block:: python

    for backend in cinderlib.Backend.backends:
        backend.refresh()

    with open('cinderlib.txt', 'w') as f:
        f.write(cinderlib.dumps())

When serializing *cinderlib* resources we'll get all the data currently
present.  This means that when serializing a volume that is attached and has
snapshots we'll get them all serialized.

There are some cases where we don't want this, such as when implementing a
persistence metadata plugin.  We should use the `to_json` and `to_jsons`
methods for such cases, as they will return a simplified serialization of the
resource containing only the data from the resource itself.

From JSON
---------

Just like we had the `json`, `jsons`, `dump`, and `dumps` methods in all the
*cinderlib* objects to serialize data, we also have the `load` method to
deserialize this data back and recreate a *cinderlib* internal representation
from JSON, be it stored in a Python string or a Python dictionary.

The `load` method is present in *Backend*, *Volume*, *Snapshot*, and
*Connection* classes as well as in the library itself.  The resource specific
`load` class method is the exact counterpart of the serialization methods, and
it will deserialize the specific resource from the class its being called from.

The library's `load` method is capable of loading anything we have serialized.
Not only can it load the full list of *Backends* with their resources, but it
can also load individual resources.  This makes it the recommended way to
deserialize any data in *cinderlib*.  By default, serialization and the
metadata storage are disconnected, so loading serialized data will not ensure
that the data is present in the persistence storage.  We can ensure that
deserialized data is present in the persistence storage passing `save=True` to
the loading method.

Considering the files we created in the earlier examples we can easily load our
whole configuration with:

.. code-block:: python

    # We must have initialized the Backends before reaching this point

    with open('cinderlib.txt', 'r') as f:
        data = f.read()
    backends = cinderlib.load(data, save=True)

And for a specific backend or an individual volume:

.. code-block:: python

    # We must have initialized the Backends before reaching this point

    with open('lvm.txt', 'r') as f:
        data = f.read()
    lvm = cinderlib.load(data, save=True)

    with open('vol.txt', 'r') as f:
        data = f.read()
    vol = cinderlib.load(data)

This is the preferred way to deserialize objects, but we could also use the
specific object's `load` method.

.. code-block:: python

    # We must have initialized the Backends before reaching this point

    with open('lvm.txt', 'r') as f:
        data = f.read()
    lvm = cinderlib.Backend.load(data)

    with open('vol.txt', 'r') as f:
        data = f.read()
    vol = cinderlib.Volume.load(data)

To dict
-------

Serialization properties and methos presented earlier are meant to store all
the data and allow reuse of that data when using drivers of different releases.
So it will include all required information to be backward compatible when
moving from release N *Cinder* drivers to release N+1 drivers.

There will be times when we'll just want to have a nice dictionary
representation of a resource, be it to log it, to display it while debugging,
or to send it from our controller application to the node where we are going to
be doing the attachment.  For these specific cases all resources, except the
*Backend* have a `to_dict` method (not property this time) that will only
return the relevant data from the resources.


Backend configuration
---------------------

When *cinderlib* serializes any object it also stores the *Backend* this object
belongs to.  For security reasons it only stores the identifier of the backend
by default, which is the `volume_backend_name`.  Since we are only storing a
reference to the *Backend*, this means that when we are going through the
deserialization process the *Backend* the object belonged to must already be
present in *cinderlib*.

This should be OK for most *cinderlib* usages, since it's common practice to
store the storage backend connection information (credentials, addresses, etc.)
in a different location than the data; but there may be situations (for example
while testing) where we'll want to store everything in the same file, not only
the *cinderlib* representation of all the storage resources but also the
*Backend* configuration required to access the storage array.

To enable the serialization of the whole driver configuration we have to
specify `output_all_backend_info=True` on the *cinderlib* initialization
resulting in a self contained file with all the information required to manage
the resources.

This means that with this configuration option we won't need to configure the
*Backends* prior to loading the serialized JSON data, we can just load the data
and *cinderlib* will automatically setup the *Backends*.
