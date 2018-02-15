====
TODO
====

There are many things that need improvements in *cinderlib*, this is a simple
list to keep track of the most relevant topics.

- Connect & attach snapshot for drivers that support it.
- Replication and failover support
- QoS
- Support custom features via extra specs
- Unit tests
- Integration tests
- Parameter validation
- Support using *cinderlib* without cinder to just handle the attach/detach
- Add .py examples
- Support other Cinder releases besides Pike
- Add support for new Attach/Detach mechanism
- Consistency Groups
- Encryption
- Support name and description attributes in Volume and Snapshot
- Verify multiattach support
- Use created_at, updated_at, and deleted_at fields
- Use a list instead of a set in Volume.snapshots so they are ordered, which
  can be useful to restore to the latest snapshot as well as to delete them in
  reverse order of creation.
- Revert to snapshot support.
- Add documentation to connect remote host.  `use_multipath_for_image_xfer` and
  the `enforce_multipath_for_image_xfer` options.
- Complete internals documentation.
- Document the code.
- Should *cinderlib* support working with sqlite instead of just RAM?
- Improve serialization to limit following of references to other objects.
