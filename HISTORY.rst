=======
History
=======

0.3.0 (2019-01-14)
------------------

- Bug fixes:

  - Detach a volume when it's unavailable.

- Features:

  - Provide better message when device is not available.
  - Backend name stored in host instead of in the AZ (backward incompatible).
  - Support multi-pool drivers.
  - Support QoS
  - Support extra specs

0.2.2 (2018-07-24)
------------------

- Features:

  - Use NOS-Brick to setup OS-Brick for non OpenStack usage.
  - Can setup persistence directly to use key-value storage.
  - Support loading objects without configured backend.
  - Support for Cinder Queens, Rocky, and Master
  - Serialization returns a compact string

- Bug fixes:

  - Workaround for Python 2 getaddrinfo bug
  - Compatibility with requests and requests-kerberos
  - Fix key-value support set_key_value.
  - Fix get_key_value to return KeyValue.
  - Fix loading object without configured backend.

0.2.1 (2018-06-14)
------------------

- Features:

  - Modify fields on connect method.
  - Support setting custom root_helper.
  - Setting default project_id and user_id.
  - Metadata persistence plugin mechanism
  - DB persistence plugin
  - No longer dependent on Cinder's attach/detach code
  - Add device_attached method to update volume on attaching node
  - Support attaching/detaching RBD volumes
  - Support changing persistence plugin after initialization
  - Add saving and refreshing object's metadata
  - Add dump, dumps methods

- Bug fixes:

  - Serialization of non locally attached connections.
  - Accept id field set to None on resource creation.
  - Disabling of sudo command wasn't working.
  - Fix volume cloning on XtremIO
  - Fix iSCSI detach issue related to privsep
  - Fix wrong size in volume from snapshot
  - Fix name & description inconsistency
  - Set created_at field on creation
  - Connection fields not being set
  - DeviceUnavailable exception
  - Multipath settings after persistence retrieval
  - Fix PyPi package created tests module
  - Fix connector without multipath info
  - Always call create_export and remove_export
  - iSCSI unlinking on disconnect

0.1.0 (2017-11-03)
------------------

* First release on PyPI.
