=======
Volumes
=======

The *Volume* class provides the abstraction layer required to perform all
operations on an existing volume, which means that there will be volume
creation operations that will be invoked from other class instances, since the
new volume we want to create doesn't exist yet and we cannot use the *Volume*
class to manage it.

Create
------

The base resource in storage is the volume, and to create one the *cinderlib*
provides three different mechanisms, each one with a different method that will
be called on the source of the new volume.

So we have:

- Empty volumes that have no resource source and will have to be created
  directly on the *Backend* via the `create_volume` method.

- Cloned volumes that will be created from a source *Volume* using its `clone`
  method.

- Volumes from a snapshot, where the creation is initiated by the
  `create_volume` method from the *Snapshot* instance.

.. note::

    *Cinder* NFS backends will create an image and not a directory where to
    store files, which falls in line with *Cinder* being a Block Storage
    provider and not filesystem provider like *Manila* is.

So assuming that we have an `lvm` variable holding an initialized *Backend*
instance we could create a new 1GB volume quite easily:

.. code-block:: python

    print('Stats before creating the volume are:')
    pprint(lvm.stats())
    vol = lvm.create_volume(1)
    pprint(lvm.stats())


Now, if we have a volume that already contains data and we want to create a new
volume that starts with the same contents we can use the source volume as the
cloning source:

.. code-block:: python

    cloned_vol = vol.clone()

Some drivers support cloning to a bigger volume, so we could define the new
size in the call and the driver would take care of extending the volume after
cloning it, this is usually tightly linked to the `extend` operation support by
the driver.

Cloning to a greater size would look like this:

.. code-block:: python

    new_size = vol.size + 1
    cloned_bigger_volume = vol.clone(size=new_size)

.. note::

    Cloning efficiency is directly linked to the storage backend in use, so it
    will not have the same performance in all backends. While some backends
    like the Ceph/RBD will be extremely efficient others may range from slow to
    being actually implemented as a `dd` operation performed by the driver
    attaching source and destination volumes.

.. code-block:: python

    vol = snap.create_volume()

.. note::

    Just like with the cloning functionality, not all storage backends can
    efficiently handle creating a volume from a snapshot.

On volume creation we can pass additional parameters like a `name` or a
`description`, but these will be irrelevant for the actual volume creation and
will only be useful to us to easily identify our volumes or to store additional
information.

Available fields with their types can be found in `Cinder's Volume OVO
definition
<https://github.com/openstack/cinder/blob/stable/queens/cinder/objects/volume.py#L71-L131>`_,
but most of them are only relevant within the full *Cinder* service.

We can access these fields as if they were part of the *cinderlib* *Volume*
instance, since the class will try to retrieve any non *cinderlib* *Volume*
from *Cinder*'s internal OVO representation.

Some of the fields we could be interested in are:

- `id`: UUID-4 unique identifier for the volume.

- `user_id`: String identifier, in *Cinder* it's a UUID, but we can choose
  here.

- `project_id`: String identifier, in *Cinder* it's a UUID, but we can choose
  here.

- `snapshot_id`: ID of the source snapshot used to create the volume.  This
  will be filled by *cinderlib*.

- `host`: Used to store the backend name information together with the host
  name where cinderlib is running.  This information is stored as a string in
  the form of *host@backend#pool*.  This is an optional parameter, and passing
  it to `create_volume` will override default value, allowing us caller to
  request a specific pool for multi-pool backends, though we recommend using
  the `pool_name` parameter instead. Issues will arise if parameter doesn't
  contain correct information.

- `pool_name`: Pool name to use when creating the volume.  Default is to use
  the first or only pool.  To know possible values for a backend use the
  `pool_names` property on the *Backend* instance.

- `size`: Volume size in GBi.

- `availability_zone`: In case we want to define AZs.

- `status`: This represents the status of the volume, and the most important
  statuses are `available`, `error`, `deleted`, `in-use`, `creating`.

- `attach_status`: This can be `attached` or `detached`.

- `scheduled_at`: Date-time when the volume was scheduled to be created.
  Currently not being used by *cinderlib*.

- `launched_at`: Date-time when the volume creation was completed.  Currently
  not being used by *cinderlib*.

- `deleted`: Boolean value indicating whether the volume has already been
  deleted.  It will be filled by *cinderlib*.

- `terminated_at`: When the volume delete was sent to the backend.

- `deleted_at`: When the volume delete was completed.

- `display_name`: Name identifier, this is passed as `name` to all *cinderlib*
  volume creation methods.

- `display_description`: Long description of the volume, this is passed as
  `description` to all *cinderlib* volume creation methods.

- `source_volid`: ID of the source volume used to create this volume.  This
  will be filled by *cinderlib*.

- `bootable`: Not relevant for *cinderlib*, but maybe useful for the
  *cinderlib* user.

- `extra_specs`: Extra volume configuration used by some drivers to specify
  additional information, such as compression, deduplication, etc.  Key-Value
  pairs are driver specific.

- `qos_specs`: Backend QoS configuration. Dictionary with driver specific
  key-value pares that enforced by the backend.

.. note::

    *Cinderlib* automatically generates a UUID for the `id` if one is not
    provided at volume creation time, but the caller can actually provide a
    specific `id`.

    By default the `id` is limited to valid UUID and this is the only kind of
    ID that is guaranteed to work on all drivers.  For drivers that support non
    UUID IDs we can instruct *cinderlib* to modify *Cinder*'s behavior and
    allow them.  This is done on *cinderlib* initialization time passing
    `non_uuid_ids=True`.

Delete
------

Once we have created a *Volume* we can use its `delete` method to permanently
remove it from the storage backend.

In *Cinder* there are safeguards to prevent a delete operation from completing
if it has snapshots (unless the delete request comes with the `cascade` option
set to true), but here in *cinderlib* we don't, so it's the callers
responsibility to delete the snapshots.

Deleting a volume with snapshots doesn't have a defined behavior for *Cinder*
drivers, since it's never meant to happen, so some storage backends delete the
snapshots, other leave them as they were, and others will fail the request.

Example of creating and deleting a volume:

.. code-block:: python

    vol = lvm.create_volume(size=1)
    vol.delete()

.. attention::

    When deleting a volume that was the source of a cloning operation some
    backends cannot delete them (since they have copy-on-write clones) and they
    just keep them as a silent volume that will be deleted when its snapshot
    and clones are deleted.

Extend
------

Many storage backends and *Cinder* drivers support extending a volume to have
more space and you can do this via the `extend` method present in your *Volume*
instance.

If the *Cinder* driver doesn't implement the extend operation it will raise a
`NotImplementedError`.

The only parameter received by the `extend` method is the new size, and this
must always be greater than the current value because *cinderlib* is not
validating this at the moment.

Example of creating, extending, and deleting a volume:

.. code-block:: python

    vol = lvm.create_volume(size=1)
    print('Vol %s has %s GBi' % (vol.id, vol.size))
    vol.extend(2)
    print('Extended vol %s has %s GBi' % (vol.id, vol.size))
    vol.delete()

Other methods
-------------

All other methods available in the *Volume* class will be explained in their
relevant sections:

- `load` will be explained together with `json`, `jsons`, `dump`, and `dumps`
  properties, and the `to_dict` method in the :doc:`serialization` section.

- `refresh` will reload the volume from the metadata storage and reload any
  lazy loadable property that has already been loaded.  Covered in the
  :doc:`serialization` and :doc:`tracking` sections.

- `create_snapshot` method will be covered in the :doc:`snapshots` section
  together with the `snapshots` attribute.

- `attach`, `detach`, `connect`, and `disconnect` methods will be explained in
  the :doc:`connections` section.
