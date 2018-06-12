==============
Initialization
==============

The cinderlib itself doesn't require an initialization, as it tries to provide
sensible settings, but in some cases we may want to modify these defaults to
fit a specific desired behavior and the library provides a mechanism to support
this.

Library initialization should be done before making any other library call,
including *Backend* initialization and loading serialized data, if we try to
do it after other calls the library will raise and `Exception`.

Provided *setup* method is `cinderlib.Backend.global_setup`, but for
convenience the library provides a reference to this class method in
`cinderlib.setup`

The method definition is as follows:

.. code-block:: python

    @classmethod
    def global_setup(cls, file_locks_path=None, root_helpers='sudo',
                     suppress_requests_ssl_warnings=True, disable_logs=True,
                     non_uuid_ids=False, output_all_backend_info=False,
                     project_id=None, user_id=None, **log_params):


The meaning of the library's configuration options are:

file_locks_path
---------------

Cinder is a complex system that can support Active-Active deployments, and each
driver and storage backend has different restrictions, so in order to
facilitate mutual exclusion it provides 3 different types of locks depending
on the scope the driver requires:

- Between threads of the same process.
- Between different process on the same host.
- In all the OpenStack deployment.

Cinderlib doesn't currently support the third type of locks, but that should
not be an inconvenience for most cinderlib usage.

Cinder uses file locks for the between process locking and cinderlib uses that
same kind of locking for the third type of locks, which is also what Cinder
uses when not deployed in an Active-Active fashion.

Parameter defaults to `None`, which will use the current directory to store all
file locks required by the drivers.

root_helper
-----------

There are some operations in *Cinder* drivers that require `sudo` privileges,
this could be because they are running Python code that requires it or because
they are running a command with `sudo`.

Attaching and detaching operations with *cinderlib* will also require `sudo`
privileges.

This configuration option allows us to define a custom root helper or disabling
all `sudo` operations passing an empty string when we know we don't require
them and we are running the process with a non passwordless `sudo` user.

Defaults to `sudo`.

suppress_requests_ssl_warnings
------------------------------

Controls the suppression of the *requests* library SSL certificate warnings.

Defaults to `True`.

non_uuid_ids
------------

As mentioned in the :doc:`volumes` section we can provide resource IDs manually
at creation time, and some drivers even support non UUID identificators, but
since that's not a given validation will reject any non UUID value.

This configuration option allows us to disable the validation on the IDs, at
the user's risk.

Defaults to `False`.

output_all_backend_info
-----------------------

Whether to include the *Backend* configuration when serializing objects.
Detailed information can be found in the :doc:`serialization` section.

Defaults to `False`.

disable_logs
------------

*Cinder* drivers are meant to be run within a full blown service, so they can
be quite verbose in terms of logging, that's why *cinderlib* disables it by
default.

Defaults to `True`.

project_id
----------

*Cinder* is a multi-tenant service, and when resources are created they belong
to a specific tenant/project.  With this parameter we can define, using a
string, an identifier for our project that will be assigned to the resources we
create.

Defaults to `cinderlib`.

user_id
-------

Within each project/tenant the *Cinder* project supports multiple users, so
when it creates a resource a reference to the user that created it is stored
in the resource.  Using this this parameter we can define, using a string, an
identifier for the user of cinderlib to be recorded in the resources.

Defaults to `cinderlib`.

other keyword arguments
-----------------------

Any other keyword argument passed to the initialization method will be
considered a *Cinder* configuration option and passed directly to all the
drivers.

This can be useful to set additional logging configuration like debug log
level, or many other advanced features.

For a list of the possible configuration options one should look into the
*Cinder* project's documentation.
