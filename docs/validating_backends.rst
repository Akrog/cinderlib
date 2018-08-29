===================
Validating a driver
===================

OK, so you have seen the project and would like to check if the Cinder driver
for your storage backend will work with *cinderlib* or not, but don't want to
spend a lot of time to do it.

In that case the best way to do it is using our functional tests with a custom
configuration file that has your driver configuration.

The environment
---------------

Before we can test anything we'll need to get our environment ready, which will
be comprised of three steps:

- Clone the *cinderlib* project:

  .. code-block:: shell

     $ git clone git://github.com/akrog/cinderlib

- Create the testing environment which will include the required Cinder code:

  .. code-block:: shell

     $ cd cinderlib
     $ tox -efunctional --notest

- Install any specific packages our driver requires.  Some Cinder drivers have
  external dependencies that need to be manually installed.  These dependencies
  can be Python package or Linux binaries.  If it's the former we will need to
  install them in the testing virtual environment we created in the previous
  step.

  For example, for the Kaminario backend we need the *krest* Python package, so
  here's how we would install the dependency.

  .. code-block:: shell

     $ source .tox/py27/bin/active
     (py27) $ pip install krest
     (py27) $ deactivate

  To see the Python dependencies for each backend we can check the
  `driver-requirements.txt
  <https://raw.githubusercontent.com/openstack/cinder/stable/queens/driver-requirements.txt>`_
  file from the Cinder project, or in *cinderlib*'s `setup.py` file listed in
  the `extras` dictionary.

  If we have binary dependencies we can copy them in `.tox/py27/bin` or just
  install them globally in our system.

The configuration
-----------------

Functional test use a YAML configuration file to get the driver configuration
as well as some additional parameters for running the tests, with the default
configuration living in the `tests/functiona/lvm.yaml` file.

The configuration file currently supports 3 key-value pairs, with only one
being mandatory.

- `logs`: Boolean value defining whether we want the Cinder code to log to
  stdout during the testing.  Defaults to `false`.

- `venv_sudo`: Boolean value that instructs the functional tests on whether we
  want to run with normal `sudo` or with a custom command that ensure that the
  virtual environment's binaries are also available.  This is not usually
  necessary, but there are some drivers that use binaries installed by a Python
  package (like the LVM that requires the `cinder-rtstool` from Cinder).  This
  is also necessary if we've installed a binary in the `.tox/py27/bin`
  directory.

- `size_precision`: Integer value describing how much precision we must use
  when comparing volume sizes.  Due to cylinder sizes some storage arrays don't
  abide 100% to the requested size of the volume.  With this option we can
  define how many decimals will be correct when testing sizes.  A value of 2
  means that the backend could create a 1.0015869140625GB volume when we
  request a 1GB volume and the tests wouldn't fail.  Default is zero, which for
  us means that it must be perfect or it will fail.

- `backends`: This is a list of dictionaries each with the configuration
  parameters that are configured in the `cinder.conf` file in Cinder.

The contents of the default configuration, excluding the comments, are:

.. code-block:: yaml

   logs: false
   venv_sudo: true
   backends:
       - volume_backend_name: lvm
         volume_driver: cinder.volume.drivers.lvm.LVMVolumeDriver
         volume_group: cinder-volumes
         target_protocol: iscsi
         target_helper: lioadm

But like the name implies, `backends` can have multiple drivers configured, and
the functional tests will run the tests on them all.

For example a configuration file with LVM, Kaminario, and XtremIO backends
would look like this:

.. code-block:: yaml

   logs: false
   venv_sudo: true
   backends:
       - volume_driver: cinder.volume.drivers.lvm.LVMVolumeDriver
         volume_group: cinder-volumes
         target_protocol: iscsi
         target_helper: lioadm
         volume_backend_name: lvm

       - volume_backend_name: xtremio
         volume_driver: cinder.volume.drivers.dell_emc.xtremio.XtremIOISCSIDriver
         use_multipath_for_image_xfer: true
         xtremio_cluster_name: CLUSTER
         san_ip: x.x.x.x
         san_login: user
         san_password: password

       - volume_backend_name: kaminario
         volume_driver: cinder.volume.drivers.kaminario.kaminario_iscsi.KaminarioISCSIDriver
         use_multipath_for_image_xfer: true
         san_ip: x.x.x.y
         san_login: user
         san_password: password

The validation
--------------

Now it's time to run the commands, for this we'll use the `tox` command passing
the location of our configuration file via environmental variable
`CL_FTESTS_CFG`:

.. code-block:: shell

   $ CL_FTEST_CFG=temp/tests.yaml tox -efunctional

   functional develop-inst-nodeps: /home/geguileo/code/cinderlib
   functional installed: You are using pip version 8.1.2, ...
   functional runtests: PYTHONHASHSEED='2093635202'
   functional runtests: commands[0] | unit2 discover -v -s tests/functional
   test_attach_detach_volume_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_attach_detach_volume_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_attach_detach_volume_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_attach_detach_volume_via_attachment_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_attach_detach_volume_via_attachment_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_attach_detach_volume_via_attachment_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_attach_volume_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_attach_volume_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_attach_volume_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_clone_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_clone_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_clone_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_times_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_times_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_times_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_volumes_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_volumes_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_multiple_volumes_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_volume_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_volume_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_connect_disconnect_volume_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_snapshot_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_snapshot_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_snapshot_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_volume_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_volume_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_create_delete_volume_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_create_snapshot_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_create_snapshot_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_create_snapshot_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_from_snapshot_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_from_snapshot_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_from_snapshot_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_create_volume_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_disk_io_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_disk_io_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_disk_io_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_extend_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_extend_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_extend_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_stats_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_stats_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_stats_on_xtremio (tests_basic.BackendFunctBasic) ... ok
   test_stats_with_creation_on_kaminario (tests_basic.BackendFunctBasic) ... ok
   test_stats_with_creation_on_lvm (tests_basic.BackendFunctBasic) ... ok
   test_stats_with_creation_on_xtremio (tests_basic.BackendFunctBasic) ... ok

   ----------------------------------------------------------------------
   Ran 48 tests in x.ys

   OK

As can be seen each test will have a meaningful name ending in the name of the
backend we have provided via the `volume_backend_name` key in the YAML file.


Reporting results
-----------------

Once you have run the tests, it's time to report the results so they can be
included in the :doc:`validated_backends` section.

To help others use the same backend and help us track how each storage driver
was tested please include the following information in your report:

- *Cinderlib* version.
- Storage Array: What hardware and firmware version were used.
- Connection type tested: iSCSI, FC, RBD, etc.
- Dependencies/Requirements for the backend: Packages, Python libraries,
  configuration files...
- Contents of the YAML file with usernames, passwords, and IPs appropriately
  masked.
- *Cinder* releases: What cinder releases have been tested.
- Additional notes: Limitations or anything worth mentioning.

To report the results of the tests please create an `issue on the project`_
with the information mentioned above and include any errors you encountered if
you did encounter any.


.. _issue on the project: https://github.com/Akrog/cinderlib/issues/new
