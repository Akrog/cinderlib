.. highlight:: shell

============
Installation
============


Stable release
--------------

The Cinder Library is an interfacing library that doesn't have any storage
driver and expects Cinder drivers to be properly installed in the system to run
properly.

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

    # yum install -y centos-release-openstack-queens
    # yum-config-manager --enable openstack-queens
    # yum update -y
    # yum install -y openstack-cinder

On RHEL and Fedora, you'll need to download and install the RDO repository RPM
to set up the OpenStack repository:

.. code-block:: console

    # yum install -y https://repos.fedorapeople.org/repos/openstack/openstack-queens/rdo-release-queens-1.noarch.rpm
    # yum-config-manager --enable openstack-queens
    # sudo yum update -y
    # yum install -y openstack-cinder

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

Container
_________

There is a docker image, in case you prefer trying the library without any
installation.

The image is called `akrog/cinderlib:stable`, and we can run Python dirrectly
with:

.. code-block:: console

   $ docker run --name=cinderlib --privileged --net=host -v /etc/iscsi:/etc/iscsi -v /dev:/dev -it akrog/cinderlib:stable python


Latest code
-----------

Container
_________

A Docker image is automatically built on every commit to the *master* branch.
Running a Python shell with the latest *cinderlib* code is as simple as:

.. code-block:: console

   $ docker run --name=cinderlib --privileged --net=host -v /etc/iscsi:/etc/iscsi -v /dev:/dev -it akrog/cinderlib python

Drivers
_______

If we don't have a packaged version or if we want to use a virtual environment
we can install the drivers from source:

.. code-block:: console

    $ virtualenv cinder
    $ source cinder/bin/activate
    $ pip install git+https://github.com/openstack/cinder.git

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

    # python setup.py install


.. _Github repo: https://github.com/akrog/cinderlib
.. _tarball: https://github.com/akrog/cinderlib/tarball/master
