Cinder Library
===============================

.. image:: https://img.shields.io/pypi/v/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://readthedocs.org/projects/cinderlib/badge/?version=latest
   :target: https://cinderlib.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

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

