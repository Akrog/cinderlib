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
- Dell EMC `VMAX`_
- `Kaminario`_ K2
- NetApp `SolidFire`_


LVM
---

- *Cinderlib version*: v0.1.0, v0.2.0
- *Cinder release*: *Pike*, *Queens*, *Rocky*
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
         target_protocol: iscsi
         target_helper: lioadm


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

  - If we don't define the `keyring` configuration parameter (must use an
    absolute path) in our `rbd_ceph_conf` to point to our `rbd_keyring_conf`
    file, we'll need the `rbd_keyring_conf` to be in `/etc/ceph/`.
  - `rbd_keyring_confg` must always be present and must follow the naming
     convention of `$cluster.client.$rbd_user.conf`.
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
- *Cinder release*: *Pike*, *Queens*, *Rocky*
- *Storage*: Dell EMC XtremIO
- *Versions*: v4.0.15-20_hotfix_3
- *Connection type*: iSCSI, FC
- *Requirements*: None
- *Tested by*: Gorka Eguileor (geguileo/akrog)

*Configuration* for iSCSI:

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

*Configuration* for FC:

.. code-block:: YAML

   logs: false
   venv_sudo: false
   backends:
       - volume_backend_name: xtremio
         volume_driver: cinder.volume.drivers.dell_emc.xtremio.XtremIOFCDriver
         xtremio_cluster_name: CLUSTER_NAME
         use_multipath_for_image_xfer: true
         san_ip: w.x.y.z
         san_login: user
         san_password: toomanysecrets


Kaminario
---------

- *Cinderlib version*: v0.1.0, v0.2.0
- *Cinder release*: *Pike*, *Queens*, *Rocky*
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


SolidFire
---------

- *Cinderlib version*: v0.1.0 with `later patch`_
- *Cinder release*: *Pike*
- *Storage*: NetApp SolidFire
- *Versions*: Unknown
- *Connection type*: iSCSI
- *Requirements*: None
- *Tested by*: John Griffith (jgriffith/j-griffith)

*Configuration*:

.. code-block:: YAML

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: solidfire
         volume_driver: cinder.volume.drivers.solidfire.SolidFireDriver
         san_ip: 192.168.1.4
         san_login: admin
         san_password: admin_password
         sf_allow_template_caching = false
         image_volume_cache_enabled = True
         volume_clear = zero


VMAX
----

- *Cinderlib version*: v0.1.0
- *Cinder release*: *Pike*, *Queens*, *Rocky*
- *Storage*: Dell EMC VMAX
- *Versions*: Unknown
- *Connection type*: iSCSI
- *Requirements*:

  - On *Pike* we need file `/etc/cinder/cinder_dell_emc_config.xml`.

- *Tested by*: Helen Walsh (walshh)

*Configuration* for *Pike*:

- *Cinderlib* functional test configuration:

  .. code-block:: YAML

     logs: false
     venv_sudo: false
     size_precision: 2
     backends:
         - image_volume_cache_enabled: True
           volume_clear: zero
           volume_backend_name: VMAX_ISCSI_DIAMOND
           volume_driver: cinder.volume.drivers.dell_emc.vmax.iscsi.VMAXISCSIDrive

- Contents of file `/etc/cinder/cinder_dell_emc_config.xml`:

  .. code-block:: XML

     <?xml version="1.0" encoding="UTF-8"?>
     <EMC>
       <RestServerIp>w.x.y.z</RestServerIp>
       <RestServerPort>8443</RestServerPort>
       <RestUserName>username</RestUserName>
       <RestPassword>toomanysecrets</RestPassword>
       <Array>000197800128</Array>
       <PortGroups>
         <PortGroup>os-iscsi-pg</PortGroup>
       </PortGroups>
       <SRP>SRP_1</SRP>
       <ServiceLevel>Diamond</ServiceLevel>
       <Workload>none</Workload>
       <SSLVerify>/opt/stack/localhost.domain.com.pem</SSLVerify>
     </EMC>

*Configuration* for *Queens* and *Rocky*:

.. code-block:: YAML

   venv_sudo: false
   size_precision: 2
   backends:
       - image_volume_cache_enabled: True
         volume_clear: zero
         volume_backend_name: VMAX_ISCSI_DIAMOND
         volume_driver: cinder.volume.drivers.dell_emc.vmax.iscsi.VMAXISCSIDriver
         san_ip: w.x.y.z
         san_rest_port: 8443
         san_login: user
         san_password: toomanysecrets
         vmax_srp: SRP_1
         vmax_array: 000197800128
         vmax_port_groups: [os-iscsi-pg]


.. _later patch: https://github.com/Akrog/cinderlib/commit/7dde24e6ccdff19de330fe826b5d449831fff2a6
