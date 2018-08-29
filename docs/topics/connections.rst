===========
Connections
===========

When talking about attaching a *Cinder* volume there are three steps that must
happen before the volume is available in the host:

1. Retrieve connection information from the host where the volume is going to
   be attached.  Here we would be getting iSCSI initiator name, IP, and similar
   information.

2. Use the connection information from step 1 and make the volume accessible to
   it in the storage backend returning the volume connection information.  This
   step entails exporting the volume and initializing the connection.

3. Attaching the volume to the host using the data retrieved on step 2.

If we are running *cinderlib* and doing the attach in the same host, then all
steps will be done in the same host.  But in many cases you may want to manage
the storage backend in one host and attach a volume in another.  In such cases,
steps 1 and 3 will happen in the host that needs the attach and step 2 on the
node running *cinderlib*.

Projects in *OpenStack* use the *OS-Brick* library to manage the attaching and
detaching processes.  Same thing happens in *cinderlib*.  The only difference
is that there are some connection types that are handled by the hypervisors in
*OpenStack*, so we need some alternative code in *cinderlib* to manage them.

*Connection* objects' most interesting attributes are:

- `connected`: Boolean that reflects if the connection is complete.

- `volume`: The *Volume* to which this instance holds the connection
  information.

- `protocol`: String with the connection protocol for this volume, ie: `iscsi`,
  `rbd`.

- `connector_info`: Dictionary with the connection information from the host
  that is attaching.  Such as it's hostname, IP address, initiator name, etc.

- `conn_info`: Dictionary with the connection information the host requires to
  do the attachment, such as IP address, target name, credentials, etc.

- `device`: If we have done a local attachment this will hold a dictionary with
  all the attachment information, such as the `path`, the `type`, the
  `scsi_wwn`, etc.

- `path`: String with the path of the system device that has been created when
  the volume was attached.


Local attach
------------

Once we have created a volume with *cinderlib* doing a local attachment is
really simple, we just have to call the `attach` method from the *Volume* and
we'll get the *Connection* information from the attached volume, and once we
are done we call the `detach` method on the *Volume*.

.. code-block:: python

    vol = lvm.create_volume(size=1)
    attach = vol.attach()
    with open(attach.path, 'w') as f:
        f.write('*' * 100)
    vol.detach()

This `attach` method will take care of everything, from gathering our local
connection information, to exporting the volume, initializing the connection,
and finally doing the local attachment of the volume to our host.

The `detach` operation works in a similar way, but performing the exact
opposite steps and in reverse.  It will detach the volume from our host,
terminate the connection, and if there are no more connections to the volume it
will also remove the export of the volume.

.. attention::

   The *Connection* instance returned by the *Volume* `attach` method also has
   a `detach` method, but this one behaves differently than the one we've seen
   in the *Volume*, as it will just perform the local detach step and not the
   termiante connection or the remove export method.

Remote connection
-----------------

For a remote connection it's a little more inconvenient at the moment, since
you'll have to manually use the *OS-Brick* library on the host that is going to
do the attachment.

.. note:: THIS SECTION IS INCOMPLETE

First we need to get the connection information on the host that is going to do
the attach:

.. code-block:: python

    import os_brick

    # Retrieve the connection information dictionary

Then we have to do the connection

.. code-block:: python

	# Create the connection
    attach = vol.connect(connector_dict)

    # Return the volume connection information


.. code-block:: python

    import os_brick

    # Do the attachment

Multipath
---------

If we want to use multipathing for local attachments we must let the *Backend*
know when instantiating the driver by passing the
`use_multipath_for_image_xfer=True`:


.. code-block:: python

    import cinderlib

    lvm = cinderlib.Backend(
        volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
        volume_group='cinder-volumes',
        target_protocol='iscsi',
        target_helper='lioadm',
        volume_backend_name='lvm_iscsi',
        use_multipath_for_image_xfer=True,
    )

Multi attach
------------

Multi attach support has just been added to *Cinder* in the Queens cycle, and
it's not currently supported by *cinderlib*.

Other methods
-------------

All other methods available in the *Snapshot* class will be explained in their
relevant sections:

- `load` will be explained together with `json`, `jsons`, `dump`, and `dumps`
  properties, and the `to_dict` method in the :doc:`serialization` section.

- `refresh` will reload the volume from the metadata storage and reload any
  lazy loadable property that has already been loaded.  Covered in the
  :doc:`serialization` and :doc:`tracking` sections.
