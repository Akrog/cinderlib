#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_cinderlib
----------------------------------

Tests for `cinderlib` module.
"""

import unittest2

import cinderlib


class TestCinderlib(unittest2.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_lib_setup(self):
        self.assertEqual(cinderlib.setup, cinderlib.Backend.global_setup)
