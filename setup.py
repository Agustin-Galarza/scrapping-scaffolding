from setuptools import setup, find_packages

setup(
    name='searcher',
    version='0.1',
    packages=find_packages(include=['scrapper','io_utils','cyberdrop']),
    install_requires=[
        'tqdm',
        'bs4',
        'requests'
    ],
    entry_points={
        'console_scripts': [
            'searcher = searcher.main:main',
            'scrapper = scrapper.main:main'
        ],
    },
)