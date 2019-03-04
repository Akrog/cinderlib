#!/bin/env python
# Copyright (c) 2017, Red Hat, Inc.
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
"""Generate Python code to initialize cinderlib based on Cinder config file

This tool generates Python code to instantiate backends using a cinder.conf
file.

It supports multiple backends as defined in enabled_backends.

This program uses the oslo.config module to load configuration options instead
of using configparser directly because drivers will need variables to have the
right type (string, list, integer...), and the types are defined in the code
using oslo.config.

 cinder-cfg-to_python cinder.conf cinderlib-conf.py

If no output is provided it will use stdout, and if we also don't provide an
input file, it will default to /etc/cinder/cinder.conf.
"""

import sys

import six

from cinderlib.cmd import cinder_to_yaml


def _to_str(value):
    if isinstance(value, six.string_types):
        return '"' + value + '"'
    return value


def convert(source, dest):
    config = cinder_to_yaml.convert(source)
    result = ['import cinderlib as cl']
    for backend in config['backends']:
        name = backend['volume_backend_name']
        name = name.replace(' ', '_').replace('-', '_')
        cfg = ', '.join('%s=%s' % (k, _to_str(v)) for k, v in backend.items())
        result.append('%s = cl.Backend(%s)' % (name, cfg))

    with open(dest, 'w') as f:
        f.write('\n\n'.join(result) + '\n')


def main():
    source = '/etc/cinder/cinder.conf' if len(sys.argv) < 2 else sys.argv[1]
    dest = '/dev/stdout' if len(sys.argv) < 3 else sys.argv[2]
    convert(source, dest)


if __name__ == '__main__':
    main()
