=========
Internals
=========

Here we'll go over some of the implementation details within *cinderlib* as
well as explanations of how we've resolved the different issues that arise from
accessing the driver's directly from outside of the cinder-volume service.

Some of the issues *cinderlib* has had to resolve are:

- *Oslo config* configuration loading.
- Cinder-volume dynamic configuration loading.
- Privileged helper service.
- DLM configuration.
- Disabling of cinder logging.
- Direct DB access within drivers.
- *Oslo Versioned Objects* DB access methods such as `refresh` and `save`.
- Circular references in *Oslo Versioned Objects* for serialization.
- Using multiple drivers in the same process.
