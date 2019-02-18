=====
Usage
=====

Thanks to the fully Object Oriented abstraction, instead of a classic method
invocation passing the resources to work on, *cinderlib* makes it easy to hit
the ground running when managing storage resources.

Once the *Cinder* and *cinderlib* packages are installed we just have to import
the library to start using it:

.. code-block:: python

    import cinderlib

.. note::

   Installing the *Cinder* package does not require to start any of its
   services (volume, scheduler, api) or auxiliary services (KeyStone, MySQL,
   RabbitMQ, etc.).

Usage documentation is not too long, and it is recommended to read it all
before using the library to be sure we have at least a high level view of the
different aspects related to managing our storage with *cinderlib*.

Before going into too much detail there are some aspects we need to clarify to
make sure our terminology is in sync and we understand where each piece fits.

In *cinderlib* we have *Backends*, that refer to a storage array's specific
connection configuration so it usually doesn't refer to the whole storage. With
a backend we'll usually have access to the configured pool.

Resources managed by *cinderlib* are *Volumes* and *Snapshots*, and a *Volume*
can be created from a *Backend*, another *Volume*, or from a *Snapshot*, and a
*Snapshot* can only be created from a *Volume*.

Once we have a volume we can create *Connections* so it can be accessible from
other hosts or we can do a local *Attachment* of the volume which will retrieve
required local connection information of this host, create a *Connection* on
the storage to this host, and then do the local *Attachment*.

Given that *Cinder* drivers are not stateless, *cinderlib* cannot be either.
That's why there is a metadata persistence plugin mechanism to provide
different ways to store resource states.  Currently we have memory and database
plugins.  Users can store the data wherever they want using the JSON
serialization mechanism or with a custom metadata plugin.

Each of the different topics are treated in detail on their specific sections:

.. toctree::
    :maxdepth: 1

    topics/initialization
    topics/backends
    topics/volumes
    topics/snapshots
    topics/connections
    topics/serialization
    topics/tracking
    topics/metadata

Auto-generated documentation is also available:

.. toctree::
   :maxdepth: 2

   api/cinderlib
