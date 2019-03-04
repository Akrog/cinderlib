#!/bin/bash
# plugin.sh - DevStack plugin.sh dispatch script for cinderlib

_XTRACE_CINDERLIB=$(set +o | grep xtrace)

function install_cinderlib {
    if use_library_from_git "cinderlib"; then
        git_clone_by_name "cinderlib"
        setup_dev_lib "cinderlib"
    else
        pip_install cinderlib
    fi
}

function generate_python_code {
    if use_library_from_git "cinderlib"; then
        sudo ${GITDIR["cinderlib"]}/tools/cinder-cfg-to-python.py $CINDER_CONF $CINDERLIB_SAMPLE
    else
        # We need to download the script since it's not part of the pypi package
        curl -s https://git.openstack.org/cgit/openstack/cinderlib/plain/tools/cinder-cfg-to-python.py | sudo python - $CINDER_CONF $CINDERLIB_SAMPLE
    fi
}

stable_compare="stable/[a-r]"
# Cinderlib only makes sense if Cinder is enabled and we are in stein or later
if [[ ! "${GITBRANCH["cinderlib"]}" =~ $stable_compare ]] && is_service_enabled cinder; then

    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing cinderlib"
        install_cinderlib

    # Plugins such as Ceph configure themselves at post-config, so we have to
    # configure ourselves at the next stage, "extra"
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Generate the cinderlib configuration
        echo_summary "Generating cinderlib initialization example python code"
        generate_python_code
    fi

    if [[ "$1" == "clean" || "$1" == "unstack" ]]; then
        echo_summary "Removing cinderlib and its code example from cinder.conf"
        sudo rm -f $CINDERLIB_SAMPLE
        pip_uninstall cinderlib
    fi
fi

# Restore xtrace
$_XTRACE_CINDERLIB
