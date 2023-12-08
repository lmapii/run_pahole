# -*- coding: utf-8 -*-
# pylint: disable=missing-module-docstring
from setuptools import setup

packages = ["run_pahole"]

package_data = {"": ["*"]}

install_requires = [
    "jsonschema>=4",
    "coloredlogs>=15.0.1",
    "argparse>=1.4.0,<2.0.0",
    "typing>=3.7.4.3",
    "typing_extensions>=4.4.0",
]

entry_points = {"console_scripts": ["run_pahole = run_pahole.cli:main"]}

setup(
    name="run-pahole",
    version="0.1.0",
    description="Wrapper for running `pahole`",
    author="Martin Lampacher",
    author_email="martin.lampacher@gmail.com",
    maintainer="None",
    maintainer_email="None",
    packages=packages,
    package_data=package_data,
    install_requires=install_requires,
    entry_points=entry_points,
    python_requires=">=3.6,<4.0",
)
