=======
History
=======

0.2.0 (2018-xx-xx)
------------------

- Features:

  - Modify fields on connect method.
  - Support setting custom root_helper.
  - Setting default project_id and user_id.
  - Persistence plugin mechanism
  - DB persistence plugin
  - No longer dependent on Cinder's attach/detach code
  - Add device_attached method to update volume on attaching node

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

0.1.0 (2017-11-03)
------------------

* First release on PyPI.
