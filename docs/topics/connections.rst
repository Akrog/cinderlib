===========
Connections
===========

When talking about attaching a *Cinder* volume there are three steps that must
happen before the volume is available in the host:

1. Retrieve connection information from the host where the volume is going to
   be attached.  Here we would be getting iSCSI initiator name and such
   information.

2. Use the connection information from step 1 and make the volume accessible to
   it in the storage backend returning the volume connection information.  This
   step entails exporting the volume and initializing the connection.

3. Attaching the volume to the host using the data retrieved on step 2.

If we are running *cinderlib* and doing the attach in the same host then all
steps will be done in the same host, but in many cases you may want to manage
the storage backend in one host and attach to another, in such cases steps 1
and 3 will happen in the host that needs the attach and step 2 on the node
running *cinderlib*.

In *OpenStack* there is a connection library called *OS-Brick* that is used by
*Cinder* and *Nova* (the compute component) to perform steps 1 and 3, but in
*cinderlib* we are not currently using it directly and instead we are
leveraging *Cinder*'s helper methods to do this for us.

This adds an unnecessary dependency on specific *Cinder* code that will be
removed in the future and also limits the usefulness of the library to abstract
*OS-Brick* library usage from *cinderlib* users.

*Connection* objects' most interesting attributes are:

- `connected`: Boolean that reflects if the connection is complete

- `volume`: The *Volume* to which this instance holds the connection
  information.

- `connector`: Connection information from the host that is attaching. Such as
  it's hostname, IP address, initiator name, etc.

- `connection_info`: The connection information the host requires to do the
  attachment, such as IP address, target name, credentials, etc.

- `attach_info`: If we have done a local attachment this will hold all the
  attachment information.


Local attach
------------

Doing a local attachment with *cinderlib* once we have created a volume is
really simple, we just have to call the `attach` method from the volume and
we'll get the *Connection* information from the attached volume, and once we
are done we call the `detach` method on the *Volume* or on the *Connection*
information that we got from `attach`.

.. code-block:: python

    vol = lvm.create_volume(size=1)
    attach = vol.attach()
    with open(attach.path, 'w') as f:
        f.write('*' * 100)
    vol.detach()

As mentioned before we could have called `attach.detach()` instead of
`vol.detach()` and it would have had the same effect.

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
`use-multipath_for_image_xfer=True`:


.. code-block:: python

    import cinderlib

    lvm = cinderlib.Backend(
        volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
        volume_group='cinder-volumes',
        iscsi_protocol='iscsi',
        iscsi_helper='lioadm',
        volume_backend_name='lvm_iscsi',
        use-multipath_for_image_xfer=True,
    )

Multi attach
------------

Multi attach support has just been added to *Cinder* in the Queens cycle, and
it's not currently supported by *cinderlib*.
