"""The skeleton imports, and its packages are the ones the contracts name."""

import importlib

import doxa

PACKAGES = [
    "doxa.governance",
    "doxa.governance.revision",
    "doxa.instruments",
    "doxa.instruments.calibration",
    "doxa.instruments.coverage",
    "doxa.solver",
    "doxa.syntax",
    "doxa.trace",
]


def test_package_imports():
    assert doxa.__doc__


def test_every_declared_package_imports():
    for name in PACKAGES:
        assert importlib.import_module(name) is not None
