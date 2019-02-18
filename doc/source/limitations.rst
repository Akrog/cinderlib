Limitations
-----------

Cinderlib works around a number of issues that were preventing the usage of the
drivers by other Python applications, some of these are:

- *Oslo config* configuration loading.
- Cinder-volume dynamic configuration loading.
- Privileged helper service.
- DLM configuration.
- Disabling of cinder logging.
- Direct DB access within drivers.
- *Oslo Versioned Objects* DB access methods such as `refresh` and `save`.
- Circular references in *Oslo Versioned Objects* for serialization.
- Using multiple drivers in the same process.

Being in its early development stages, the library is in no way close to the
robustness or feature richness that the Cinder project provides.  Some of the
more noticeable limitations one should be aware of are:

- Most methods don't perform argument validation so it's a classic GIGO_
  library.

- The logic has been kept to a minimum and higher functioning logic is expected
  to be handled by the caller: Quotas, tenant control, migration, etc.

- Limited test coverage.

- Only a subset of Cinder available operations are supported by the library.

Besides *cinderlib's* own limitations the library also inherits some from
*Cinder's* code and will be bound by the same restrictions and behaviors of the
drivers as if they were running under the standard *Cinder* services.  The most
notorious ones are:

- Dependency on the *eventlet* library.

- Behavior inconsistency on some operations across drivers.  For example you
  can find drivers where cloning is a cheap operation performed by the storage
  array whereas other will actually create a new volume, attach the source and
  new volume and perform a full copy of the data.

- External dependencies must be handled manually. So users will have to take
  care of any library, package, or CLI tool that is required by the driver.

- Relies on command execution via *sudo* for attach/detach operations as well
  as some CLI tools.

.. _GIGO: https://en.wikipedia.org/wiki/Garbage_in,_garbage_out
