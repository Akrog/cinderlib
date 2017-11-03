#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'cinder>=11.0',
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='cinderlib',
    version='0.1.0',
    description=("Cinder Library allows using storage drivers outside of "
                 "Cinder."),
    long_description=readme + '\n\n' + history,
    author="Gorka Eguileor",
    author_email='geguileo@redhat.com',
    url='https://github.com/akrog/cinderlib',
    packages=[
        'cinderlib',
    ],
    package_dir={'cinderlib':
                 'cinderlib'},
    include_package_data=True,
    install_requires=requirements,
    license="Apache Software License 2.0",
    zip_safe=False,
    keywords='cinderlib',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
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
    test_suite='tests',
    tests_require=test_requirements
)
