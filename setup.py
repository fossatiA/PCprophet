# !/usr/bin/env python3

from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup_args = dict(
    name='PCProphet',
    version='0.0.1',
    packages=find_packages(),
    scripts=[
        'collapse.py',
        'differential.py',
        'exceptions.py',
        'generate_features.py',
        'go_fdr.py',
        'io_.py',
        'hypothesis.py',
        'mcl.py',
        'init.py'
        'map_to_database.py',
        'mcl.py',
        'merge.py',
        'parse_GO.py',
        'main.py',
        'plots.py',
        'predict.py',
        'stats_.py',
        'validate_input.py',
    ],
    # long_description=long_description,
    license='MIT',
    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=['scipy>=1.1', 'pandas', 'sklearn', 'networkX'],
    package_data={
        'PCprophet': ['go_term_class.txt', 'go-basic.obo', 'rf_equal.clf'],
    },
    # metadata to display on PyPI
    author='Andrea Fossati',
    author_email='fossati@imsb.biol.ethz.ch',
    description='Software toolset for analysis of co-fractionation data',
    keywords=['proteomics', 'machine-learning', 'signal-processing'],
    url='https://github.com/fossatiA/PCProphet/',
    project_urls={
        'Bug Tracker': 'https://github.com/fossatiA/PCProphet/',
        'Documentation': 'https://github.com/fossatiA/PCProphet/',
        'Source Code': 'https://github.com/fossatiA/PCProphet/',
    },
    platforms="Linux, Mac OS X, Windows",
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Modified BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    entry_points={
        'console_scripts': [
            'PCprophet=PCprophet.app:main',
        ],
}
)

setup(**setup_args)
