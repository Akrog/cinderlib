This directory contains the cinderlib DevStack plugin.

To configure cinderlib with DevStack, you will need to enable this plugin by
adding one line to the [[local|localrc]] section of your local.conf file.

To enable the plugin, add a line of the form:

    enable_plugin cinderlib <GITURL> [GITREF]

where

    <GITURL> is the URL of a cinderlib repository
    [GITREF] is an optional git ref (branch/ref/tag).  The default is master.

For example:

    enable_plugin cinderlib https://git.openstack.org/openstack/cinderlib

Another example using Stein's stable branch:

    enable_plugin cinderlib https://git.openstack.org/openstack/cinderlib stable/stein

The cinderlib DevStack plugin will install cinderlib from Git by default, but
it can be installed from PyPi using the `CINDERLIB_FROM_GIT` configuration
option.

    CINDERLIB_FROM_GIT=False

The plugin will also generate the code equivalent to the deployed Cinder's
configuration in `$CINDERLIB_SAMPLE_DIR/cinderlib.py` which defaults to the
same directory where the Cinder configuration is saved.

For more information, see the [DevStack plugin documentation](https://docs.openstack.org/devstack/latest/plugins.html).
