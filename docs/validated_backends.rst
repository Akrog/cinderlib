=================
Validated drivers
=================

The *Cinder* project has a large number of storage drivers, and all the drivers
have their own CI to validate that they are working as expected.

For *cinderlib* this is more complicated, as we don't have the resources of the
*Cinder* project.  We rely on contributors who have access to the hardware to
test if the storage backend works with *cinderlib*.

.. note:: If you have access to storage hardware supported by *Cinder* not
   present in here and you would like to test if *cinderlib* works, please
   follow the :doc:`validating_backends` section and report your results.

Currently the following backends have been verified:

- `LVM`_ with LIO
- `Ceph`_
- Dell EMC `XtremIO`_
- `Kaminario`_ K2


LVM
---

- *Cinderlib version*: v0.1.0, v0.2.0
- *Cinder release*: *Pike*
- *Storage*: LVM with LIO
- *Connection type*: iSCSI
- *Requirements*:  None
- *Tested by*: Gorka Eguileor (geguileo/akrog)

*Configuration*:

.. code-block:: YAML

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: lvm
         volume_driver: cinder.volume.drivers.lvm.LVMVolumeDriver
         volume_group: cinder-volumes
         iscsi_protocol: iscsi
         iscsi_helper: lioadm


Ceph
----

- *Cinderlib version*: v0.2.0
- *Cinder release*: *Pike*
- *Storage*: Ceph/RBD
- *Versions*: Luminous v12.2.5
- *Connection type*: RBD
- *Requirements*:

  - `ceph-common` package
  - `ceph.conf` file
  - Ceph keyring file

- *Tested by*: Gorka Eguileor (geguileo/akrog)
- *Notes*:

  - Driver implementation requires `rbd_keyring_conf` to be in `/etc/ceph/` and
    have the name `ceph.client.$rbd_user.conf`.
  - Current driver cannot delete a snapshot if there's a dependent (a volume
    created from it exists).

*Configuration*:

.. code-block:: YAML

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: ceph
         volume_driver: cinder.volume.drivers.rbd.RBDDriver
         rbd_user: cinder
         rbd_pool: volumes
         rbd_ceph_conf: tmp/ceph.conf
         rbd_keyring_conf: /etc/ceph/ceph.client.cinder.keyring


XtremIO
-------

- *Cinderlib version*: v0.1.0, v0.2.0
- *Cinder release*: *Pike*
- *Storage*: Dell EMC XtremIO
- *Versions*: v4.0.15-20_hotfix_3
- *Connection type*: iSCSI
- *Requirements*: None
- *Tested by*: Gorka Eguileor (geguileo/akrog)

*Configuration*:

.. code-block:: YAML

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: xtremio
         volume_driver: cinder.volume.drivers.dell_emc.xtremio.XtremIOISCSIDriver
         xtremio_cluster_name: CLUSTER_NAME
         use_multipath_for_image_xfer: true
         san_ip: w.x.y.z
         san_login: user
         san_password: toomanysecrets


Kaminario
---------

- *Cinderlib version*: v0.1.0, v0.2.0
- *Cinder release*: *Pike*
- *Storage*: Kaminario K2
- *Versions*: VisionOS v6.0.72.10
- *Connection type*: iSCSI
- *Requirements*:

  - `krest` Python package from PyPi

- *Tested by*: Gorka Eguileor (geguileo/akrog)

*Configuration*:

.. code-block:: YAML

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: kaminario
         volume_driver: cinder.volume.drivers.kaminario.kaminario_iscsi.KaminarioISCSIDriver
         san_ip: w.x.y.z
         san_login: user
         san_password: toomanysecrets
         use_multipath_for_image_xfer: true
