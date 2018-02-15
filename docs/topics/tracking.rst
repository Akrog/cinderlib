Resource tracking
-----------------

*Cinderlib* users will surely have their own variables to keep track of the
*Backends*, *Volumes*, *Snapshots*, and *Connections*, but there may be cases
where this is not enough, be it because we are in a place in our code where we
don't have access to the original variables, because we want to iterate all
instances, or maybe we are running some manual tests and we have lost the
reference to a resource.  F

For these cases we can use *cinderlib's* various tracking systems to access the
resources.  These tracking systems are also used by *cinderlib* in the
serialization process.

*Cinderlib* keeps track of all:

- Initialized *Backends*.
- Existing volumes in a *Backend*.
- Connections to a volume.
- Local attachment to a volume.
- Snapshots for a given volume.
- Known volumes in this run, even deleted ones.
- Known snapshots in this run, even delete ones.
- Connections made in this run, even disconnected ones.

Initialized *Backends* are stored in a dictionary in `Backends.backends` using
the `volume_backend_name` as key.

Existing volumes in a *Backend* are stored in the *Backend* instance's
`volumes` attribute as a set.

Connections to a *Volume* are stored in the *Volume* instance's `connections`
attribute as a list.

The local attachment *Connection* of a volume is stored in the *Volume*
instance's `local_attach` attribute.

Existing *Snapshots* for a *Volume* are stored as a set in the *Volume*
instance's `snapshots` attribute.

Besides the existing resources we also have access to all resources that
*cinderlib* has known about in this run through the `objects` attribute that
can be found in `Volume`, `Snapshot`, and `Connection` classes.

We can use this information to display the status of all the resources we've
created and destroyed in this run:

.. code-block:: python

    for vol in cinderlib.Volume.objects:
        print('Volume %s is currently %s' % (vol.id, vol.status)

    for snap in cinderlib.Snapshot.objects:
        print('Snapshot %s for volume %s is currently %s' %
              (snap.id, snap.volume.id, snap.status))

    for conn in cinderlib.Connection.objects:
        print('Connection from %s with ip %s to volume %s is %s' %
              (conn.connector['host'], conn.connector['ip'],
               conn.volume.id, conn.status))
