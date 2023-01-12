#!/usr/bin/env python3

import doctest
import importlib
import sys
import unittest

if __name__ == "__main__":
    command = sys.argv[1:]
    if command == ["build"]:
        suite = unittest.TestSuite()
        suite.addTest(doctest.DocTestSuite(
            importlib.import_module("projects"),
            optionflags=doctest.REPORT_NDIFF|doctest.FAIL_FAST
        ))
        if not unittest.TextTestRunner().run(suite).wasSuccessful():
            sys.exit(1)
    else:
        sys.exit(f"ERROR: Unknown command {command}.")
