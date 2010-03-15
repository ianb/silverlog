from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='SilverLog',
      version=version,
      description="Log file viewer for Silver Lining",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ian Bicking',
      author_email='ianb@mozilla.com',
      url='http://cloudsilverlining.org/silverlog/',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'WebOb',
          'DevAuth',
          'Tempita',
          'Routes',
      ],
      )
