#!/usr/bin/env python

from setuptools import setup

setup(
    version = '1.0',
    name = 'xampler',
    description = 'Extending ASP with sampling with parity constraints.',
    author = 'Flavio Everardo',
    license = 'MIT',
    packages = ['xampler'],
    test_suite = 'xampler.tests',
    zip_safe = False,
    entry_points = {
        'console_scripts': [
            'xampler = xampler:main',
        ]
    }
)

