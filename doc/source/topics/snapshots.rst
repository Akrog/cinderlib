=========
Snapshots
=========

The *Snapshot* class provides the abstraction layer required to perform all
operations on an existing snapshot, which means that the snapshot creation
operation must be invoked from other class instance, since the new snapshot we
want to create doesn't exist yet and we cannot use the *Snapshot* class to
manage it.

Create
------

Once we have a *Volume* instance we are ready to create snapshots from it, and
we can do it for attached as well as detached volumes.

.. note::

    Some drivers, like the NFS, require assistance from the Compute service for
    attached volumes, so there is currently no way of doing this with
    *cinderlib*

Creating a snapshot can only be performed by the `create_snapshot` method from
our *Volume* instance, and once we have created a snapshot it will be tracked
in the *Volume* instance's `snapshots` set.

Here is a simple code to create a snapshot and use the `snapshots` set to
verify that both, the returned value by the call as well as the entry added to
the `snapshots` attribute, reference the same object and that the `volume`
attribute in the *Snapshot* is referencing the source volume.

.. code-block:: python

    vol = lvm.create_volume(size=1)
    snap = vol.create_snapshot()
    assert snap is list(vol.snapshots)[0]
    assert vol is snap.volume

Delete
------

Once we have created a *Snapshot* we can use its `delete` method to permanently
remove it from the storage backend.

Deleting a snapshot will remove its reference from the source *Volume*'s
`snapshots` set.

.. code-block:: python

    vol = lvm.create_volume(size=1)
    snap = vol.create_snapshot()
    assert 1 == len(vol.snapshots)
    snap.delete()
    assert 0 == len(vol.snapshots)

Other methods
-------------

All other methods available in the *Snapshot* class will be explained in their
relevant sections:

- `load` will be explained together with `json`, `jsons`, `dump`, and `dumps`
  properties, and the `to_dict` method in the :doc:`serialization` section.

- `refresh` will reload the volume from the metadata storage and reload any
  lazy loadable property that has already been loaded.  Covered in the
  :doc:`serialization` and :doc:`tracking` sections.

- `create_volume` method has been covered in the :doc:`volumes` section.
