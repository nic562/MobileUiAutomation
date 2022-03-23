from setuptools import setup

from ui_auto import __version__


def parse_requirements(filename):
    """ load requirements from a pip requirements file. (replacing from pip.req import parse_requirements)"""
    content = (line.strip() for line in open(filename))
    return [line for line in content if line and not line.startswith("#")]


setup(
    name='MobileUiAutomation',
    packages=['ui_auto'],
    version=__version__,
    author='NicholasChen',
    author_email='nic562@gmail.com',
    license='Apache License 2.0',
    url='https://github.com/nic562/MobileUiAutomation',
    description='UI自动化基础库，底层基于AirTest，adb等',
    keywords=['android', 'adb', 'AirTest'],
    install_requires=parse_requirements('requirements.txt'),
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
