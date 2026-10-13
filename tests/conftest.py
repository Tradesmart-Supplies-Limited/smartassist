"""Lets the tests import the `core` package when pytest is run from the project folder."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
