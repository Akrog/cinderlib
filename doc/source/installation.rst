.. highlight:: shell

============
Installation
============

The Cinder Library is an interfacing library that doesn't have any storage
driver code, so it expects Cinder drivers to be installed in the system to run
properly.

We can use the latest stable release or the latest code from master branch.


Stable release
--------------

Drivers
_______

For Red Hat distributions the recommendation is to use RPMs to install the
Cinder drivers instead of using `pip`.  If we don't have access to the
`Red Hat OpenStack Platform packages
<https://www.redhat.com/en/technologies/linux-platforms/openstack-platform>`_
we can use the `RDO community packages <https://www.rdoproject.org/>`_.

On CentOS, the Extras repository provides the RPM that enables the OpenStack
repository. Extras is enabled by default on CentOS 7, so you can simply install
the RPM to set up the OpenStack repository:

.. code-block:: console

    # yum install -y centos-release-openstack-rocky
    # yum install -y openstack-cinder

On RHEL and Fedora, you'll need to download and install the RDO repository RPM
to set up the OpenStack repository:

.. code-block:: console

    # yum install -y https://www.rdoproject.org/repos/rdo-release.rpm
    # yum install -y openstack-cinder


We can also install directly from source on the system or a virtual environment:

.. code-block:: console

    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install git+git://github.com/openstack/cinder.git@stable/rocky

Library
_______

To install Cinder Library we'll use PyPI, so we'll make sure to have the `pip`_
command available:

.. code-block:: console

    # yum install -y python-pip
    # pip install cinderlib

This is the preferred method to install Cinder Library, as it will always
install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


Latest code
-----------

Drivers
_______

If we don't have a packaged version or if we want to use a virtual environment
we can install the drivers from source:

.. code-block:: console

    $ virtualenv cinder
    $ source cinder/bin/activate
    $ pip install git+git://github.com/openstack/cinder.git

Library
_______

The sources for Cinder Library can be downloaded from the `Github repo`_ to use
the latest version of the library.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/akrog/cinderlib

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/akrog/cinderlib/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ virtualenv cinder
    $ python setup.py install

.. _Github repo: https://github.com/openstack/cinderlib
.. _tarball: https://github.com/openstack/cinderlib/tarball/master
