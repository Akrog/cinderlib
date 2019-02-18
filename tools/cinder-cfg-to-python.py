#!/bin/env python
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

from cinderlib.tests.functional import cinder_to_yaml


def _to_str(value):
    if isinstance(value, six.string_types):
        return '"' + value + '"'
    return value


def main(source, dest):
    config = cinder_to_yaml.convert(source)
    result = ['import cinderlib as cl']
    for backend in config['backends']:
        name = backend['volume_backend_name']
        name = name.replace(' ', '_').replace('-', '_')
        cfg = ', '.join('%s=%s' % (k, _to_str(v)) for k, v in backend.items())
        result.append('%s = cl.Backend(%s)' % (name, cfg))

    with open(dest, 'w') as f:
        f.write('\n\n'.join(result) + '\n')


if __name__ == '__main__':
    source = '/etc/cinder/cinder.conf' if len(sys.argv) < 2 else sys.argv[1]
    dest = '/dev/stdout' if len(sys.argv) < 3 else sys.argv[2]
    main(source, dest)
