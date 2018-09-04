#!/bin/env python
"""Generate functional tests YAML configuration files from Cinder config file

Functional tests require a YAML file with the backend configuration parameters.
To facilitate running them on a deployment that already has Cinder configured
(ie: devstack) this program can translate from cinder.conf to a valid YAML
file that can be used to run cinderlib functional tests.

This program uses the oslo.config module to load configuration options instead
of using configparser directly because drivers will need variables to have the
right type (string, list, integer...), and the types are defined in the code
using oslo.config.
"""

import sys
import yaml

from six.moves import configparser

from cinder.cmd import volume
volume.objects.register_all()  # noqa

from cinder.volume import configuration as config
from cinder.volume import manager


def convert(cinder_source, yaml_dest):
    result_cfgs = []

    # Manually parse the Cinder configuration file so we know which options are
    # set.
    parser = configparser.ConfigParser()
    parser.read(cinder_source)
    enabled_backends = parser.get('DEFAULT', 'enabled_backends')
    backends = [name.strip() for name in enabled_backends.split(',') if name]

    volume.CONF(('--config-file', cinder_source), project='cinder')

    for backend in backends:
        options_present = parser.options(backend)

        # Dynamically loading the driver triggers adding the specific
        # configuration options to the backend_defaults section
        cfg = config.Configuration(manager.volume_backend_opts,
                                   config_group=backend)
        driver_ns = cfg.volume_driver.rsplit('.', 1)[0]
        __import__(driver_ns)

        # Use the backend_defaults section to extract the configuration for
        # options that are present in the backend section and add them to
        # the backend section.
        opts = volume.CONF._groups['backend_defaults']._opts
        known_present_options = [opt for opt in options_present if opt in opts]
        volume_opts = [opts[option]['opt'] for option in known_present_options]
        cfg.append_config_values(volume_opts)

        # Now retrieve the options that are set in the configuration file.
        result_cfgs.append({option: cfg.safe_get(option)
                            for option in known_present_options})

    result = {'backends': result_cfgs}
    # Write the YAML to the destination
    with open(yaml_dest, 'w') as f:
        yaml.dump(result, f)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('Incorrect number of arguments\n')
        exit(1)
    convert(sys.argv[1], sys.argv[2])
