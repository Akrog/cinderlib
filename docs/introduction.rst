Cinder Library
==============

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

Cinder Library is a Python library that allows using storage drivers provided
by Cinder outside of OpenStack and without needing to run the Cinder service,
so we don't need Keystone, MySQL, or RabbitMQ services to control our storage.

The library is currently in an early development stage and can be considered as
a proof of concept and not a finished product at this moment, so please
carefully go over the limitations section to avoid surprises.

Due to the limited access to Cinder backends and time constraints the list of
drivers that have been manually tested, and using the existing limited
functional tests, are:

- LVM with LIO
- Dell EMC XtremIO
- Dell EMC VMAX
- Kaminario K2
- Ceph/RBD
- NetApp SolidFire

Features
--------

* Use a Cinder driver without running a DBMS, Message broker, or Cinder
  services.
* Using multiple simultaneous drivers on the same program.
* Stateless: Support full serialization of objects and context to JSON or
  string so the state can be restored.
* Metadata persistence plugin mechanism.
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

Demo
----

.. raw:: html

  <script type="text/javascript" src="https://asciinema.org/a/TcTR7Lu7jI0pEsd9ThEn01l7n.js"
          id="asciicast-TcTR7Lu7jI0pEsd9ThEn01l7n" async data-autoplay="false"
          data-loop="false"></script>

Limitations
-----------

Being in its early development stages the library is in no way close to the
robustness or feature richness that the Cinder project provides.  Some of the
more noticeable limitations one should be aware of are:

- Most methods don't perform argument validation so it's a classic GIGO_
  library.

- The logic has been kept to a minimum and higher functioning logic is expected
  to be handled by the caller.

- There is no CI, or unit tests for that matter, and certainly nothing so fancy
  as third party vendor CIs, so things could be broken at any point.  We only
  have some automated, yet limited, functional tests.

- Only a subset of Cinder available operations are supported by the library.

- Access to a small number of storage arrays has limited the number of drivers
  that have been verified to work with cinderlib.

Besides *cinderlib's* own limitations the library also inherits some from
*Cinder's* code and will be bound by the same restrictions and behaviors of the
drivers as if they were running under the standard *Cinder* services.  The most
notorious ones are:

- Dependency on the *eventlet* library.

- Behavior inconsistency on some operations across drivers.  For example you
  can find drivers where cloning is a cheap operation performed by the storage
  array whereas other will actually create a new volume, attach the source and
  new volume and perform a full copy of the data.

- External dependencies must be handled manually. So we'll have to take care of
  any library, package, or CLI tool that is required by the driver.

- Relies on command execution via *sudo* for attach/detach operations as well
  as some CLI tools.

.. _GIGO: https://en.wikipedia.org/wiki/Garbage_in,_garbage_out
