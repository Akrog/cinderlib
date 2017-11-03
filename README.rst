Cinder Library
===============================



.. image:: https://img.shields.io/pypi/v/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://img.shields.io/travis/akrog/cinderlib.svg
   :target: https://travis-ci.org/akrog/cinderlib

.. image:: https://readthedocs.org/projects/cinderlib/badge/?version=latest
   :target: https://cinderlib.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/cinderlib.svg
   :target: https://pypi.python.org/pypi/cinderlib

.. image:: https://pyup.io/repos/github/akrog/cinderlib/shield.svg
     :target: https://pyup.io/repos/github/akrog/cinderlib/
     :alt: Updates

.. image:: https://img.shields.io/:license-apache-blue.svg
   :target: http://www.apache.org/licenses/LICENSE-2.0


Introduction
------------

Cinder Library is a Python library that allows using storage drivers outside of
Cinder.

* Free software: Apache Software License 2.0
* Documentation: https://cinderlib.readthedocs.io.

This library is currently at an Alpha status and is primarily intended as a
proof of concept at this stage.  While some drivers have been manually
validated most drivers have not, so there's a good chance that they could
experience issues.

When using this library one should be aware that this is in no way close to the
robustness or feature richness that the Cinder project provides.  Some of the
more obvious limitations are:

* There are no argument validation on the methods so it's a classic GIGO_
  library.
* The logic has been kept to a minimum and higher functioning logic is expected
  to be in the caller. For example you can delete a volume that still has
  snapshots, and the end results will depend on the Cinder driver and the
  storage array, so you will have some that will delete the snapshots and
  others that will leave them there.
* There is no CI, or unit tests for that matter, and certainly nothing so fancy
  as third party vendor CIs, so things being broken could be considered the
  norm.
* Only a subset number of basic operations are supported by the library.

The minimum version of Cinder required by this library is Pike; although,
depending on my my availability, I may make the library support Ocata as well.

Since it's using Cinder's code the library is still bound by the same
restrictions and behaviors of the drivers running under the standard Cinder
services, which means that not all operations will behave consistently across
drivers.  For example you can find drivers where cloning is a cheap operation
performed by the storage array whereas other will actually create a new volume,
attach the source and the new volume and perform a full copy of the data.

If a driver in Cinder requires external libraries or packages they will also
be required by the library and will need to be manually installed.

For more detailed information please refer to the `official project
documentation`_ and `OpenStack's Cinder volume driver configuration
documentation`_.

Due to the limited access to Cinder backends and time constraints the list of
drivers that have been manually tested are (I'll try to test more):

- LVM
- XtremIO
- Kaminario

If you try the library with another storage array I would appreciate a note on
the library version, Cinder release, and results of your testing.

Features
--------

* Use a Cinder driver without running a DBMS, Message broker, or Cinder
  service.
* Using multiple simultaneous drivers on the same program.
* Stateless: Support full serialization of objects and context to json or
  string so the state can be restored.
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


.. _GIGO: https://en.wikipedia.org/wiki/Garbage_in,_garbage_out
.. _official project documentation: https://readthedocs.org/projects/cinderlib/badge/?version=latest
.. _OpenStack's Cinder volume driver configuration documentation: https://docs.openstack.org/cinder/latest/configuration/block-storage/volume-drivers.html
