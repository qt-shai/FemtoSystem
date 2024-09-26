import unittest
from HW_wrapper import Zelux

class MyTestCase(unittest.TestCase):
    def test_find_zelux_devices(self):
        self.assertGreater(len(Zelux.get_available_devices()),0,"No Zelux devices")


if __name__ == '__main__':
    unittest.main()
