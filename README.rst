Cinder Library
===============================

.. image:: https://img.shields.io/pypi/v/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://readthedocs.org/projects/cinderlib/badge/?version=latest
   :target: https://cinderlib.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://img.shields.io/docker/build/akrog/cinderlib.svg
   :target: https://hub.docker.com/r/akrog/cinderlib

.. image:: https://img.shields.io/docker/automated/akrog/cinderlib.svg
   :target: https://hub.docker.com/r/akrog/cinderlib/builds

.. image:: https://img.shields.io/:license-apache-blue.svg
   :target: http://www.apache.org/licenses/LICENSE-2.0


Introduction
------------

Cinder Library is a Python library that allows using storage drivers outside of
Cinder.

* Free software: Apache Software License 2.0
* Documentation: https://cinderlib.readthedocs.io.

This library is currently in Alpha stage and is primarily intended as a proof
of concept at this stage.  While some drivers have been manually validated most
drivers have not, so there's a good chance that they could experience issues.

When using this library one should be aware that this is in no way close to the
robustness or feature richness that the Cinder project provides, for detailed
information on the current limitations please refer to the documentation.

Due to the limited access to Cinder backends and time constraints the list of
drivers that have been manually tested are (I'll try to test more):

- LVM with LIO
- Dell EMC XtremIO
- Dell EMC VMAX
- Kaminario K2
- Ceph/RBD
- NetApp SolidFire

If you try the library with another storage array I would appreciate a note on
the library version, Cinder release, and results of your testing.

Features
--------

* Use a Cinder driver without running a DBMS, Message broker, or Cinder
  service.
* Using multiple simultaneous drivers on the same program.
* Basic operations support:

  - Create volume
  - Delete volume
  - Extend volume
  - Clone volume
  - Create snapshot
  - Delete snapshot
  - Create volume from snapshot
  - Connect volume
  - Disconnect volume
  - Local attach
  - Local detach
  - Validate connector

* Code should support multiple concurrent connections to a volume, though this
  has not yet been tested.
* Metadata persistence plugin:

  - Stateless: Caller stores JSON serialization.
  - Database: Metadata is stored in a database: MySQL, PostgreSQL, SQLite...
  - Custom plugin: Metadata is stored in another metadata storage.

Demo
----

.. raw:: html

  <a href="https://asciinema.org/a/TcTR7Lu7jI0pEsd9ThEn01l7n?autoplay=1"
  target="_blank"><img
  src="https://asciinema.org/a/TcTR7Lu7jI0pEsd9ThEn01l7n.png"/></a>

Example
-------

The following example uses CentOS 7 and the Cinder LVM driver, which should be
the easiest to setup and test.

First you need to setup your system.

The easiest way to set things up is using Vagrant + libvirt using the provided
docker example, as it will create a small VM (1GB and 1CPU) and provision
everything so we can run a Python interpreter in a cinderlib container:

.. code-block:: shell

   $ cd examples/docker
   $ vagrant up
   $ vagrant ssh -c 'sudo docker exec -it cinderlib python'

If we don't want to use the example we have to setup an LVM VG to use:

.. code-block:: shell

    $ sudo dd if=/dev/zero of=cinder-volumes bs=1048576 seek=22527 count=1
    $ sudo lodevice=`losetup --show -f ./cinder-volumes`
    $ sudo vgcreate cinder-volumes $lodevice
    $ sudo vgscan --cache

Now we can install everything on baremetal:

    $ sudo yum install -y centos-release-openstack-queens
    $ test -f  /etc/yum/vars/contentdir || echo centos >/etc/yum/vars/contentdir
    $ sudo yum install -y openstack-cinder targetcli python-pip
    $ sudo pip install cinderlib

Or run it in a container.  To be able to run it in a container we need to
change our host's LVM configuration and set `udev_rules = 0` and
`udev_sync = 0` before we start the container:

.. code-block:: shell

   $ sudo docker run --name=cinderlib --privileged --net=host \
     -v /etc/iscsi:/etc/iscsi \
     -v /dev:/dev \
     -v /etc/lvm:/etc/lvm \
     -v /var/lock/lvm:/var/lock/lvm \
     -v /lib/modules:/lib/modules:ro \
     -v /run:/run \
     -v /var/lib/iscsi:/var/lib/iscsi \
     -v /etc/localtime:/etc/localtime:ro \
     -v /root/cinder:/var/lib/cinder \
     -v /sys/kernel/config:/configfs \
     -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
     -it akrog/cinderlib:latest python

Or install things on baremetal/VM:

.. code-block:: shell

    $ sudo yum install -y centos-release-openstack-queens
    $ test -f  /etc/yum/vars/contentdir || echo centos >/etc/yum/vars/contentdir
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
                     target_protocol='iscsi',
                     target_helper='lioadm',
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
    vol = backends[0].volumes[0]
    # Volume no longer knows that the attach is local, so we cannot do
    # vol.detach(), but we can get the connection and use it.
    conn = vol.connections[0]
    # Physically detach the volume from the node
    conn.detach()
    # Unmap the volume and remove the export
    conn.disconnect()

    # Get the snapshot and delete it
    snap = vol.snapshots[0]
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
