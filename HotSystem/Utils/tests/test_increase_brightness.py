from Common import *
import unittest
class TestFastRGBPlot(unittest.TestCase):
    def setUp(self):
        pass
    def test_increase_brightness(self):
        increase_brightness(r"Q:\QT-Quantum_Optic_Lab\expData\scan\DSM2\2024_9_12_19_1_1scan_DSM2_ZELUX.png",
                            r"Q:\QT-Quantum_Optic_Lab\expData\scan\DSM2\2024_9_12_19_1_1scan_DSM2_ZELUXi.png", 10)
if __name__ == "__main__":
    unittest.main()
