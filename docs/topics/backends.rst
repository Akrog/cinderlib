========
Backends
========

The *Backend* class provides the abstraction to access a storage array with an
specific configuration, which usually constraints our ability to operate on the
backend to a single pool.

.. note::

    While some drivers have been manually validated most drivers have not, so
    there's a good chance that using any non tested driver will show unexpected
    behavior.

    If you are testing *cinderlib* with a non verified backend you should use
    an exclusive pool for the validation so you don't have to be so careful
    when creating resources as you know that everything within that pool is
    related to *cinderlib* and can be deleted using the vendor's management
    tool.

    If you try the library with another storage array I would appreciate a note
    on the library version, Cinder release, and results of your testing.

Initialization
--------------

Before we can have access to an storage array we have to initialize the
*Backend*, which only has one parameter defined and all other parameters are
not defined in the method prototype:

.. code-block:: python

    class Backend(object):
        def __init__(self, volume_backend_name, **driver_cfg):

There are two arguments that we'll always have to pass on the initialization,
one is the `volume_backend_name` that is the unique identifier that *cinderlib*
will use to identify this specific driver initialization, so we'll need to make
sure not to repeat the name, and the other one is the `volume_driver` which
refers to the Python path that points to the *Cinder* driver.

All other *Backend* configuration options are free-form keyword arguments
because each driver and storage array requires different information to
operate, some require credentials to be passed as parameters while others use a
file, some require the control address as well as the data addresses. This
behavior is inherited from the *Cinder* project.

To find what configuration options are available and which ones are compulsory
the best is going to the Vendor's documentation or to the `OpenStack's Cinder
volume driver configuration documentation`_.

.. attention::

    Some drivers have external dependencies which we must satisfy before
    initializing the driver or it may fail either on the initialization or when
    running specific operations.  For example Kaminario requires the *krest*
    Python library, and Pure requires *purestorage* Python library.

    Python library dependencies are usually documented in the
    `driver-requirements.txt file
    <https://github.com/openstack/cinder/blob/master/driver-requirements.txt>`_,
    as for the CLI required tools we'll have to check in the Vendor's
    documentation.

Cinder only supports using one driver at a time, as each process only handles
one backend, but *cinderlib* has overcome this limitation and supports having
multiple *Backends* simultaneously.

Let's see now initialization examples of some storage backends:

LVM
---

.. code-block:: python

    import cinderlib

    lvm = cinderlib.Backend(
        volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
        volume_group='cinder-volumes',
        iscsi_protocol='iscsi',
        iscsi_helper='lioadm',
        volume_backend_name='lvm_iscsi',
    )

XtremIO
-------

.. code-block:: python

    import cinderlib

    xtremio = cinderlib.Backend(
        volume_driver='cinder.volume.drivers.dell_emc.xtremio.XtremIOISCSIDriver',
        san_ip='10.10.10.1',
        xtremio_cluster_name='xtremio_cluster',
        san_login='xtremio_user',
        san_password='xtremio_password',
        volume_backend_name='xtremio',
    )

Kaminario
---------

.. code-block:: python

    import cinderlib

    kaminario = cl.Backend(
        volume_driver='cinder.volume.drivers.kaminario.kaminario_iscsi.KaminarioISCSIDriver',
        san_ip='10.10.10.2',
        san_login='kaminario_user',
        san_password='kaminario_password',
        volume_backend_name='kaminario_iscsi',
    )

Available Backends
------------------

Usual procedure is to initialize a *Backend* and store it in a variable at the
same time so we can use it to manage our storage backend, but there are cases
where we may have lost the reference or we are in a place in our code where we
don't have access to the original variable.

For these situations we can use *cinderlib's* tracking of *Backends* through
the `backends` class dictionary where all created *Backends* are stored using
the `volume_backend_name` as the key.

.. code-block:: python

    for backend in cinderlib.Backend.backends.values():
        initialized_msg = '' if backend.initialized else 'not '
        print('Backend %s is %sinitialized with configuration: %s' %
              (backend.id, initialized_msg, backend.config))

Stats
-----

In *Cinder* all cinder-volume services periodically report the stats of their
backend to the cinder-scheduler services so they can do informed placing
decisions on operations such as volume creation and volume migration.

Some of the keys provided in the stats dictionary include:

- `driver_version`
- `free_capacity_gb`
- `storage_protocol`
- `total_capacity_gb`
- `vendor_name volume_backend_name`

Additional information can be found in the `Volume Stats section
<https://docs.openstack.org/cinder/pike/contributor/drivers.html#volume-stats>`_
within the Developer's Documentation.

Gathering stats is a costly operation for many storage backends, so we have the
possibility of retrieving the cached value that was retrieved the last time.

Here's an example of the output from the LVM *Backend*:

.. code-block:: python

    >>> from pprint import pprint
    >>> pprint(lvm.stats())
    {'driver_version': '3.0.0',
     'pools': [{'QoS_support': False,
                'filter_function': None,
                'free_capacity_gb': 20.9,
                'goodness_function': None,
                'location_info': 'LVMVolumeDriver:router:cinder-volumes:thin:0',
                'max_over_subscription_ratio': 20.0,
                'multiattach': False,
                'pool_name': 'LVM',
                'provisioned_capacity_gb': 0.0,
                'reserved_percentage': 0,
                'thick_provisioning_support': False,
                'thin_provisioning_support': True,
                'total_capacity_gb': '20.90',
                'total_volumes': 1}],
     'sparse_copy_volume': True,
     'storage_protocol': 'iSCSI',
     'vendor_name': 'Open Source',
     'volume_backend_name': 'LVM'}

Available volumes
-----------------

Just like the *Backend* class keeps track of all the *Backend* instances in the
`backends` class attribute, each *Backend* instance will keep track of all the
volumes that have been created in the *Backend*, regardless of how they have
been created, and still exist in the storage backend.  So all volumes that have
been successfully deleted will no longer be there.

We can access the *Volumes* with the `volumes` instance attribute of type
`set`.

So assuming that we have an `lvm` variable holding an initialized *Backend*
instance where we have created volumes we could list them with:

.. code-block:: python

    for vol in lvm.volumes:
        print('Volume %s has %s GB' % (vol.id, vol.size))

.. note::

    The `volumes` attribute variable will only hold the volumes that are known
    to this *cinderlib*, be it because we have created the volumes in this run
    or because we have loaded them from a serialized source.

    This should not be confused with a listing of the volumes within the pool
    we are using.

Attributes
----------

The *Backend* class has no attributes of interest besides the `backends`
mentioned above and the `id`, `config`, and JSON related properties we'll see
later in the :doc:`serialization` section.

The `id` property refers to the `volume_backend_name`, which is also the key
used in the `backends` class attribute.

The `config` property will return a dictionary with only the volume backend's
name by default to limit unintended exposure of backend credentials on
serialization.  If we want it to return all the configuration options we need
to pass `output_all_backend_info=True` on *cinderlib* initialization.

If we try to access any non-existent attribute in the *Backend*, *cinderlib*
will understand we are trying to access a *Cinder* driver attribute and will
try to retrieve it from the driver's instance.  This is the case with the
`initialized` property we accessed in the backends listing example.


Other methods
-------------

All other methods available in the *Backend* class will be explained in their
relevant sections:

- `load` and `load_backend` will be explained together with `json` and `jsons`
  properties in the :doc:`serialization` section.

- `create_volume` method will be covered in the :doc:`volumes` section.

- `validate_connector` will be explained in the :doc:`connections` section.

- `global_setup` has been covered in the :doc:`initialization` section.

.. _OpenStack's Cinder volume driver configuration documentation: https://docs.openstack.org/cinder/latest/configuration/block-storage/volume-drivers.html
