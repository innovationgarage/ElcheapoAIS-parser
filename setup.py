#!/usr/bin/env python

import setuptools

setuptools.setup(name='elcheapoais-parser',
      version='0.1',
      description='NMEA parser for ElcheapoAIS',
      long_description='NMEA parser system for ElcheapoAIS',
      long_description_content_type="text/markdown",
      author='Egil Moeller',
      author_email='egil@innovationgarage.no',
      url='https://github.com/innovationgarage/ElCheapoAIS-parser',
      packages=setuptools.find_packages(),
      install_requires=[
          "libais==0.17",
          "PyGObject",
          "dbus-python==1.2.12",
          "pyserial"
      ],
      include_package_data=True,
      entry_points='''
      [console_scripts]
      elcheapoais-parser = elcheapoais_parser:main
      '''
  )
