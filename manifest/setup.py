#!/usr/bin/env python2.7

from setuptools import setup

setup(
  name='updater',
  version='0.0.1',
  description='Updates manifests',
  author='Baughn',
  license='MIT',
  scripts=['update.py'],
  install_requires=[
    'beautifulsoup==3.2.1',
    'lxml==3.4.4',
    'futures==3.0.5',
  ],
)
