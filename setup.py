#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

with open('README.rst') as readme_file:
    readme = readme_file.read()

# Remove the demo for the PyPi package
start = readme.index('Demo\n----')
end = readme.index('Example\n-------')
readme = readme[:start] + readme[end:]


with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'cinder>=11.0',
]

test_requirements = [
    # TODO: put package test requirements here
]

extras = {
    # DRBD
    'drbd': ['dbus', 'drbdmanage'],
    # HPE 3PAR
    '3par': ['hpe3parclient>=4.1.0'],
    # Kaminario
    'kaminario': ['krest>=1.3.0'],
    # Pure
    'pure': ['purestorage>=1.6.0'],
    # Dell EMC VMAX
    'vmax': ['pyOpenSSL>=1.0.0'],
    # IBM DS8K
    'ds8k': ['pyOpenSSL>=1.0.0'],
    # HPE Lefthand
    'lefthand': ['python-lefthandclient>=2.0.0'],
    # Fujitsu Eternus DX
    'eternus': ['pywbem>=0.7.0'],
    # IBM XIV
    'xiv': ['pyxcli>=1.1.5'],
    # RBD/Ceph
    'rbd': ['rados', 'rbd'],
    # Dell EMC VNX
    'vnx': ['storops>=0.4.8'],
    # Violin
    'violin': ['vmemclient>=1.1.8'],
    # INFINIDAT
    'infinidat': ['infinisdk', 'capacity', 'infi.dtypes.wwn',
                  'infi.dtypes.iqn'],
}

setuptools.setup(
    name='cinderlib',
    version='0.3.1',
    description=("Cinder Library allows using storage drivers outside of "
                 "Cinder."),
    long_description=readme + '\n\n' + history,
    author="Gorka Eguileor",
    author_email='geguileo@redhat.com',
    url='https://github.com/akrog/cinderlib',
    packages=setuptools.find_packages(exclude=['tmp', 'cinderlib/tests']),
    include_package_data=False,
    install_requires=requirements,
    extras_require=extras,
    license="Apache Software License 2.0",
    zip_safe=False,
    keywords='cinderlib',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='unittest2.collector',
    tests_require=test_requirements,
    entry_points={
        'cinderlib.persistence.storage': [
            'memory = cinderlib.persistence.memory:MemoryPersistence',
            'db = cinderlib.persistence.dbms:DBPersistence',
            'memory_db = cinderlib.persistence.dbms:MemoryDBPersistence',
        ],
    },
)
