from __future__ import annotations

import os
import sys


def pytest_configure(config):
    # Modify sys.path for all tests
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../bin')))


def pytest_ignore_collect(path, config):
    ignore_paths = ['tests/cli-cps/old']
    for ignore_path in ignore_paths:
        if ignore_path in str(path):
            return True
    return False
