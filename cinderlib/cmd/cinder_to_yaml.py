# Copyright (c) 2018, Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from os import path
import yaml

from six.moves import configparser

from cinder.cmd import volume
volume.objects.register_all()  # noqa

from cinder.volume import configuration as config
from cinder.volume import manager


def convert(cinder_source, yaml_dest=None):
    result_cfgs = []

    if not path.exists(cinder_source):
        raise Exception("Cinder config file %s doesn't exist" % cinder_source)

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
    if yaml_dest:
        # Write the YAML to the destination
        with open(yaml_dest, 'w') as f:
            yaml.dump(result, f)
    return result
