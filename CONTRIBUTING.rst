============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/akrog/cinderlib/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Storage backend and configuration used (replacing sensitive information with
  asterisks).
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues and the :doc:`todo` file for features.  Anything
tagged with "enhancement" and "help wanted" is open to whoever wants to
implement it.

Write tests
~~~~~~~~~~~

We currently lack decent test coverage, so feel free to look into our existing
tests to add missing tests, because any test that increases our coverage is
more than welcome.

Write Documentation
~~~~~~~~~~~~~~~~~~~

Cinder Library could always use more documentation, whether as part of the
official Cinder Library docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/akrog/cinderlib/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up `cinderlib` for local development.

1. Fork the `cinderlib` repo on GitHub.
2. Clone your fork locally:

.. code-block:: shell

    $ git clone git@github.com:YOUR_NAME_HERE/cinderlib.git

3. Install tox:

.. code-block:: shell

    $ sudo dnf install python2-tox

4. Generate a virtual environment, for example for Python 2.7:

.. code-block:: shell

    $ tox --notest -epy27

5. Create a branch for local development:

.. code-block:: shell

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

6. When you're done making changes, you can check that your changes pass flake8
   and unit tests with:

.. code-block:: shell

    $ tox -eflake8
    $ tox -epy27

   Or if you don't want to create a specific environment for flake8 you can run
   things directly without tox:

.. code-block:: shell

    $ source .tox/py27/bin/activate
    $ flake8 cinderlib tests
    $ python setup.py test

7. Run functional tests at least with the default LVM configuration:

.. code-block:: shell

    $ tox -efunctional

   To run the LVM functional tests you'll need to have the expected LVM VG
   ready.  This can be done using the script we have for this purpose (assuming
   we are in the *cinderlib* base directory):

.. code-block:: shell

    $ mkdir temp
    $ cd temp
    $ sudo ../tools/lvm-prepare.sh

   The default configuration for the functional tests can be found in the
   `tests/functional/lvm.yaml` file.  For additional information on this file
   format and running functional tests please refer to the
   :doc:`validating_backends` section.

   And preferably with all the backends you have at your disposal:

.. code-block:: shell

    $ CL_FTESTS_CFG=temp/my-test-config.yaml tox -efunctional

8. Commit your changes making sure the commit message is descriptive enough,
   covering the patch changes as well as why the patch might be necessary.  The
   commit message should also conform to the `50/72 rule
   <https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html>`_.

    $ git add .
    $ git commit


9. Push your branch to GitHub:

.. code-block:: shell

    $ git push origin name-of-your-bugfix-or-feature

10. Submit a pull request through the GitHub website.

LVM Backend
-----------

You may not have a fancy storage array, but that doesn't mean that you cannot
use *cinderlib*, because you can always the LVM driver.  Here we are going to
see how to setup an LVM backend that we can use with *cinderlib*.

Before doing anything you need to make sure you have the required package, for Fedora, CentOS, and RHEL this will be the `targetcli` package, and for Ubuntu the `lio-utils` package.

.. code-block:: shell

    $ sudo yum install targetcli

Then we'll need to create your "storage backend", which is actually just a file
on your normal filesystem.  We'll create a 22GB file with only 1MB currently
allocated (this is worse for performance, but better for space), and then we'll
mount it as a loopback device and create a PV and VG on the loopback device.

.. code-block:: shell

    $ dd if=/dev/zero of=temp/cinder-volumes bs=1048576 seek=22527 count=1
    $ sudo lodevice=`losetup --show -f ./cinder-volumes`
    $ sudo pvcreate $lodevice
    $ sudo vgcreate cinder-volumes $lodevice
    $ sudo vgscan --cache

There is a script included in the repository that will do all this for us, so
we can just call it from the location where we want to create the file:

.. code-block:: shell

    $ sudo tools/lvm-prepare.sh

Now we can use this LVM backend in *cinderlib*:

.. code-block:: python

    import cinderlib as cl
    from pprint import pprint as pp

    lvm = cl.Backend(volume_driver='cinder.volume.drivers.lvm.LVMVolumeDriver',
                     volume_group='cinder-volumes',
                     target_protocol='iscsi',
                     target_helper='lioadm',
                     volume_backend_name='lvm_iscsi')

    vol = lvm.create_volume(size=1)

    attach = vol.attach()
    pp('Volume %s attached to %s' % (vol.id, attach.path))
    vol.detach()

    vol.delete()

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
3. The pull request should work for Python 2.7, 3.3, 3.4 and 3.5, and for PyPy.
   Check https://travis-ci.org/akrog/cinderlib/pull_requests and make sure that
   the tests pass for all supported Python versions.

Tips
----

To run a subset of tests:

.. code-block:: shell

    $ source .tox/py27/bin/activate
    $ python -m unittest tests.test_cinderlib.TestCinderlib.test_lib_setup
