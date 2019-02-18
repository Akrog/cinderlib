Resource tracking
-----------------

*Cinderlib* users will surely have their own variables to keep track of the
*Backends*, *Volumes*, *Snapshots*, and *Connections*, but there may be cases
where this is not enough, be it because we are in a place in our code where we
don't have access to the original variables, because we want to iterate all
instances, or maybe we are running some manual tests and we have lost the
reference to a resource.

For these cases we can use *cinderlib's* various tracking systems to access the
resources.  These tracking systems are also used by *cinderlib* in the
serialization process.  They all used to be in memory, but some will now reside
in the metadata persistence storage.

*Cinderlib* keeps track of all:

- Initialized *Backends*.
- Existing volumes in a *Backend*.
- Connections to a volume.
- Local attachment to a volume.
- Snapshots for a given volume.

Initialized *Backends* are stored in a dictionary in `Backends.backends` using
the `volume_backend_name` as key.

Existing volumes in a *Backend* are stored in the persistence storage, and can
be lazy loaded using the *Backend* instance's `volumes` property.

Existing *Snapshots* for a *Volume* are stored in the persistence storage, and
can be lazy loaded using the *Volume* instance's `snapshots` property.

Connections to a *Volume* are stored in the persistence storage, and can be
lazy loaded using the *Volume* instance's `connections` property.

.. note:: Lazy loadable properties will only load the value the first time we
   access them.  Successive accesses will just return the cached value.  To
   retrieve latest values for them as well as for the instance we can use the
   `refresh` method.

The local attachment *Connection* of a volume is stored in the *Volume*
instance's `local_attach` attribute and is stored in memory, so unloading the
library will lose this information.

We can easily use all these properties to display the status of all the
resources we've created:

.. code-block:: python

    # If volumes lazy loadable property was already loaded, refresh it
    lvm_backend.refresh()

    for vol in lvm_backend.volumes:
        print('Volume %s is currently %s' % (vol.id, vol.status)

        # Refresh volume's snapshots and connections if previously lazy loaded
        vol.refresh()

        for snap in vol.snapshots:
            print('Snapshot %s for volume %s is currently %s' %
                  (snap.id, snap.volume.id, snap.status))

        for conn in vol.connections:
            print('Connection from %s with ip %s to volume %s is %s' %
                  (conn.connector_info['host'], conn.connector_info['ip'],
                   conn.volume.id, conn.status))
