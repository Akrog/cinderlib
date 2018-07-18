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

You can either use a container:

.. code-block:: shell

   $ docker run --name=cinderlib --privileged --net=host -v /etc/iscsi:/etc/iscsi -v /dev:/dev -it akrog/cinderlib python

Or install things on baremetal/VM:

.. code-block:: shell

    $ sudo yum install -y centos-release-openstack-pike
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
