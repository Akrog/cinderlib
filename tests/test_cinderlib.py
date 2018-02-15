#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_cinderlib
----------------------------------

Tests for `cinderlib` module.
"""

import unittest

from cinderlib import cinderlib


class TestCinderlib(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_lib_setup(self):
        self.assertEqual(cinderlib.setup, cinderlib.Backend.global_setup)
