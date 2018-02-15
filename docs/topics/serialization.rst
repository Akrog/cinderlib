=============
Serialization
=============

A *Cinder* driver is stateless on itself, but it still requires the right data
to work, and that's why the cinder-volume service takes care of storing the
state in the DB.  This means that *cinderlib* will have to simulate the DB for
the drivers, as some operations actually return additional data that needs to
be kept and provided to any operation that follows.

During runtime all this information is stored in RAM, but what happens between
runs if we have not removed all our resources?  And what will happen on a
system crash?  What will happen is that *cinderlib* will lose all the data and
will no longer be able to manage any of the resource, leaving them stranded in
the storage backend.

What we have here is a requirement to provide a way to store the internal
*cinderclient* data, but that's not the only thing we'll want, as many systems
will require a mechanism to support over the wire transmission of *cinderlib*
objects.  To solve this problem *cinderlib* provides a JSON encoding mechanism
that allows serialization and deserialization of its objects.

For the serialization process we have two type of methods, one called `json`
that converts to a JSON stored in a Python dictionary, and another called
`jsons` that will return a Python string representation.  And for the
deserialization we have just one type of method called `load`.

To JSON
-------

As we mentioned before we have `json` and `jsons` methods, and these exist in
all *cinderlib* objects: *Backend*, *Volume*, *Snapshot*, and *Connection* as
well as in the library itself.

Current *cinderlib* serialization implementation is suboptimal for many cases
since we cannot limit how deep the serialization will go when there are other
objects references.  This means that if we serialize a *Snapthot* this will
return not only the *Snapshot* information but also the information from the
*Volume* referenced in the *Snapshot*'s `volume` attribute, and when
serializing this *Volume* we will also serialize the `snapshots` field that
contain all the other snapshots as well as all its *Connections*.  So in the
end a simple serialization of a *Snapshot* resulted in a JSON of the *Volume*
with all its *Snapshots*.

.. note::

    We don't have to worry about circular references since *cinderlib* is
    prepared to handle them.

Due to this limitation the serialization is mostly useful, at this point, to
store all the information from a *Volume*, from a *Backend*, or from all the
*Backends*.

Here is an easy way to save all the *Backend's* resources information from
*cinderlib*:

.. code-block:: python

    with open('cinderlib.txt', 'w') as f:
        f.write(cinderlib.jsons())

In a similar way we can also store a single *Backend* or a single *Volume*:

.. code-block:: python

    vol = lvm.create_volume(size=1)

    with open('lvm.txt', 'w') as f:
        f.write(lvm.jsons())

    with open('vol.txt', 'w') as f:
        f.write(vol.jsons())

From JSON
---------

Just like we had the `json` and `jsons` methods in all the *cinderlib* objects,
we'll also have the `load` method to recreate a *cinderlib* internal
representation from JSON, be it stored in a Python string or a Python
dictionary.

So we have a `load` method in *Backend*, *Volume*, *Snapshot*, and *Connection*
as well as in the library itself, but here the library's `load` method is
different that it's `json` and `jsons` counterpart, as it will deserialize any
kind of *cinderlib* object.

Considering the files we created in the earlier examples we can easily load our
whole configuration with:

.. code-block:: python

    # We must have initialized the Backends before reaching this point

    with open('cinderlib.txt', 'r') as f:
        data = f.read()
    backends = cinderlib.load(data)

And for a specific backend or an individual volume:

.. code-block:: python

    # We must have initialized the Backends before reaching this point

    with open('lvm.txt', 'r') as f:
        data = f.read()
    lvm = cinderlib.load(data)

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

Backend configuration
---------------------

When *cinderlib* serializes any object it also stores the *Backend* this object
belongs to, and by default and for security reasons, it only stores the
identifier of the backend, which is the `volume_backend_name`.  Since we are
only storing a reference to the *Backend* this means that when you are going
through the deserialization process you require that the *Backend* the object
belonged to already present in *cinderlib*.

This should be OK for most *cinderlib* usages, since it's common practice to
store you storage backend connection information (credentials, addresses, etc.)
in a different location than your data, but there may be situations (for
example while testing) where we'll want to store everything in the same file,
not only the *cinderlib* representation of all the storage resources but also
the *Backend* configuration required to access the storage array.

To enable the serialization of the whole driver configuration we have to
specify `output_all_backend_info=True` on the *cinderlib* initialization
resulting in a self contained file with all the information required to manage
the resources.

This means that with this configuration option we won't need to configure the
*Backends* prior to loading the serialized JSON data, we can just load the data
and *cinderlib* will automatically setup the *Backends*.
