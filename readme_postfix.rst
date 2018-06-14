Example
-------

The following example uses CentOS 7 and the Cinder LVM driver, which should be
the easiest to setup and test.

First you need to setup your system:

.. code-block:: shell

    $ sudo yum install -y centos-release-openstack-pike
    $ sudo yum install -y openstack-cinder targetcli python-pip
    $ sudo pip install cinderlib
    $ sudo dd if=/dev/zero of=cinder-volumes bs=1048576 seek=22527 count=1
    $ sudo lodevice=`losetup --show -f ./cinder-volumes`
    $ sudo pvcreate $lodevice
    $ sudo vgcreate cinder-volumes $lodevice
    $ sudo vgscan --cache

Then you need to run `python`  with a passwordless sudo user (required to
control LVM and do the attach) and execute:

.. code-block:: python

    import cinderlib as cl
    from pprint import pprint as pp

    # We setup the library to setup the driver configuration when serializing
    cl.setup(output_all_backend_info=True)

    # Initialize the LVM driver
    lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                     volume_group='cinder-volumes',
                     iscsi_protocol='iscsi',
                     iscsi_helper='lioadm',
                     volume_backend_name='lvm_iscsi')

    # Show the LVM backend stats
    pp(lvm.stats())

    # Create a 1GB volume
    vol = lvm.create_volume(1, name='lvm-vol')

    # Export, initialize, and do a local attach of the volume
    attach = vol.attach()

    pp('Volume %s attached to %s' % (vol.id, attach.path))

    # Snapshot it
    snap = vol.create_snapshot('lvm-snap')

    # Show the JSON string
    pp(vol.jsons)

    # Save the whole environment to a file
    with open('cinderlib-test.txt', 'w') as f:
        f.write(cl.dumps())

    # Exit python
    exit()

Now we can check that the logical volume is there, exported, and attached to
our system:

.. code-block:: shell

    # lvdisplay
    # targetcli ls
    # iscsiadm -m session
    # lsblk

And now let's run a new `python` interpreter and clean things up:

.. code-block:: python

    import cinderlib as cl

    # Get the whole environment up
    with open('cinderlib-test.txt') as f:
        backends = cl.load(f.read(), save=True)

    # Get the volume reference we loaded from file and detach
    vol = list(backends[0].volumes)[0]
    vol.detach()

    # Get the snapshot and delete it
    snap = list(vol.snapshots)[0]
    snap.delete()

    # Finally delete the volume
    vol.delete()

We should confirm that the logical volume is no longer there, there's nothing
exported or attached to our system:

.. code-block:: shell

    # lvdisplay
    # targetcli ls
    # iscsiadm -m session
    # lsblk

.. _GIGO: https://en.wikipedia.org/wiki/Garbage_in,_garbage_out
.. _official project documentation: https://readthedocs.org/projects/cinderlib/badge/?version=latest
.. _OpenStack's Cinder volume driver configuration documentation: https://docs.openstack.org/cinder/latest/configuration/block-storage/volume-drivers.html
