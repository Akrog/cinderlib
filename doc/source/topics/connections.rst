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

For a remote connection, where you don't have the driver configuration or
access to the management storage network, attaching and detaching volumes is a
little more inconvenient, and how you do it will depend on whether you have
access to the metadata persistence storage or not.

In any case the general attach flow looks something like this:

- Consumer gets connector information from its host.
- Controller receives the connector information from the consumer.  -
  Controller exports and maps the volume using the connector information and
  gets the connection information needed to attach the volume on the consumer.
- The consumer gets the connection information.  - The consumer attaches the
  volume using the connection information.

With access to the metadata persistence storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this case things are easier, as you can use the persistence storage to pass
information between the consumer and the controller node.

Assuming you have the following variables:

- `persistence_config` configuration of your metadata persistence storage.

- `node_id` unique string identifier for your consumer nodes that doesn't
  change between reboots.

- `cinderlib_driver_configuration` is a dictionary with the Cinder backend
  configuration needed by cinderlib to connect to the storage.

- `volume_id` ID of the volume we want to attach.

The consumer node must store its connector properties on start using the
key-value storage provided by the persistence plugin:

.. code-block:: python

   import cinderlib as cl

   cl.setup(persistence_config=persistence_config)

   kv = cl.Backend.persistence.get_key_values(node_id)
   if not kw:
       storage_nw_ip = socket.gethostbyname(socket.gethostname())
       connector_dict = cl.get_connector_properties('sudo', storage_nw_ip,
                                                    True, False)
       value = json.dumps(connector_dict, separators=(',', ':'))
       kv = cl.KeyValue(node_id, value)
       cl.Backend.persistence.set_key_value(kv)

Then when we want to attach a volume to `node_id` the controller can retrieve
this information using the persistence plugin and export and map the volume for
the specific host.

.. code-block:: python

   import cinderlib as cl

   cl.setup(persistence_config=persistence_config)
   storage = cl.Backend(**cinderlib_driver_configuration)

   kv = cl.Backend.persistence.get_key_values(node_id)
   if not kv:
       raise Exception('Unknown node')
   connector_info = json.loads(kv[0].value)
   vol = storage.Volume.get_by_id(volume_id)
   vol.connect(connector_info, attached_host=node_id)

Once the volume has been exported and mapped, the connection information is
automatically stored by the persistence plugin and the consumer host can attach
the volume:

.. code-block:: python

   vol = storage.Volume.get_by_id(volume_id)
   connection = vol.connections[0]
   connection.attach()
   print('Volume %s attached to %s' % (vol.id, connection.path))

When attaching the volume the metadata plugin will store changes to the
Connection instance that are needed for the detaching.

No access to the metadata persistence storage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is more inconvenient, as you'll have to handle the data exchange manually
as well as the *OS-Brick* library calls to do the attach/detach.

First we need to get the connection information on the host that is going to do
the attach:

.. code-block:: python

   from os_brick.initiator import connector

   connector_dict = connector.get_connector_properties('sudo', storage_nw_ip,
                                                       True, False)

Now we need to pass this connector information dictionary to the controller
node.  This part will depend on your specific application/system.

In the controller node, once we have the contents of the `connector_dict`
variable we can export and map the volume and get the info needed by the
consumer:

.. code-block:: python

   import cinderlib as cl

   cl.setup(persistence_config=persistence_config)
   storage = cl.Backend(**cinderlib_driver_configuration)

   vol = storage.Volume.get_by_id(volume_id)
   conn = vol.connect(connector_info, attached_host=node_id)
   connection_info = conn.connection_info

We have to pass the contents of `connection_info` information to the consumer
node, and that node will use it to attach the volume:

.. code-block:: python

    import os_brick
    from os_brick.initiator import connector

    connector_dict = connection_info['connector']
    conn_info = connection_info['conn']
    protocol = conn_info['driver_volume_type']

    conn = connector.InitiatorConnector.factory(
        protocol, 'sudo', user_multipath=True,
        device_scan_attempts=3, conn=connector_dict)
    device = conn.connect_volume(conn_info['data'])
    print('Volume attached to %s' % device.get('path'))

At this point we have the `device` variable that needs to be stored for the
disconnection, so we have to either store it on the consumer node, or pass it
to the controller node so we can save it with the connector info.

Here's an example on how to save it on the controller node:

.. code-block:: python

    conn = vol.connections[0]
    conn.device = device
    conn.save()

.. warning:: At the time of this writing this mechanism doesn't support RBD
   connections, as this support is added by cinderlib itself.

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

Multi attach support has been added to *Cinder* in the Queens cycle, and it's
not currently supported by *cinderlib*.

Other methods
-------------

All other methods available in the *Snapshot* class will be explained in their
relevant sections:

- `load` will be explained together with `json`, `jsons`, `dump`, and `dumps`
  properties, and the `to_dict` method in the :doc:`serialization` section.

- `refresh` will reload the volume from the metadata storage and reload any
  lazy loadable property that has already been loaded.  Covered in the
  :doc:`serialization` and :doc:`tracking` sections.
