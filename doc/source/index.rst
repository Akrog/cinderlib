Welcome to Cinder Library's documentation!
==========================================

.. image:: https://img.shields.io/pypi/v/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://img.shields.io/pypi/pyversions/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://img.shields.io/:license-apache-blue.svg
   :target: http://www.apache.org/licenses/LICENSE-2.0

|

The Cinder Library, also known as cinderlib, is a Python library that leverages
the Cinder project to provide an object oriented abstraction around Cinder's
storage drivers to allow their usage directly without running any of the Cinder
services or surrounding services, such as KeyStone, MySQL or RabbitMQ.

The library is intended for developers who only need the basic CRUD
functionality of the drivers and don't care for all the additional features
Cinder provides such as quotas, replication, multi-tenancy, migrations,
retyping, scheduling, backups, authorization, authentication, REST API, etc.

The library was originally created as an external project, so it didn't have
the broad range of backend testing Cinder does, and only a limited number of
drivers were validated at the time.  Drivers should work out of the box, and
we'll keep a list of drivers that have added the cinderlib functional tests to
the driver gates confirming they work and ensuring they will keep working.

Features
--------

* Use a Cinder driver without running a DBMS, Message broker, or Cinder
  service.

* Using multiple simultaneous drivers on the same application.

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
  - Extra Specs for specific backend functionality.
  - Backend QoS
  - Multi-pool support

* Metadata persistence plugins:

  - Stateless: Caller stores JSON serialization.
  - Database: Metadata is stored in a database: MySQL, PostgreSQL, SQLite...
  - Custom plugin: Caller provides module to store Metadata and cinderlib calls
    it when necessary.

Example
-------

The following code extract is a simple example to illustrate how cinderlib
works.  The code will use the LVM backend to create a volume, attach it to the
local host via iSCSI, and finally snapshot it:

.. code-block:: python

    import cinderlib as cl

    # Initialize the LVM driver
    lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                     volume_group='cinder-volumes',
                     target_protocol='iscsi',
                     target_helper='lioadm',
                     volume_backend_name='lvm_iscsi')

    # Create a 1GB volume
    vol = lvm.create_volume(1, name='lvm-vol')

    # Export, initialize, and do a local attach of the volume
    attach = vol.attach()

    print('Volume %s attached to %s' % (vol.id, attach.path))

    # Snapshot it
    snap = vol.create_snapshot('lvm-snap')

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2

   installation
   usage
   contributing
   limitations
