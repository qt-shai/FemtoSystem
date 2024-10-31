import unittest
from HW_wrapper import Keysight33500B, AttoScannerWrapper  # Assuming you have the AWG wrapper
from SystemConfig import InstrumentsAddress


class TestAttoScannerWrapper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up the Keysight 33500B AWG and AttoScannerWrapper instances before running the tests.
        """
        cls.awg = Keysight33500B(address=InstrumentsAddress.KEYSIGHT_AWG.value)  # Replace with actual address
        cls.atto_scanner = AttoScannerWrapper(cls.awg, max_travel_x=40.0, max_travel_y=40.0)

    @classmethod
    def tearDownClass(cls):
        """
        Clean up and close connections after all tests.
        """
        cls.atto_scanner.disconnect()

    def test_move_absolute(self):
        """
        Test moving the AWG to absolute positions.
        """
        # Move X (Channel 1) to 10 microns
        self.atto_scanner.MoveABSOLUTE(channel=1, position=10.0)
        voltage_x = self.atto_scanner.get_current_voltage(channel=1)
        expected_voltage_x = 10.0 / 40.0  # Convert microns to voltage
        self.assertAlmostEqual(voltage_x, expected_voltage_x, places=2, msg=f"Voltage mismatch for X: {voltage_x} != {expected_voltage_x}")

        # Move Y (Channel 2) to 20 microns
        self.atto_scanner.MoveABSOLUTE(channel=2, position=20.0)
        voltage_y = self.atto_scanner.get_current_voltage(channel=2)
        expected_voltage_y = 20.0 / 40.0  # Convert microns to voltage
        self.assertAlmostEqual(voltage_y, expected_voltage_y, places=2, msg=f"Voltage mismatch for Y: {voltage_y} != {expected_voltage_y}")

    def test_move_with_velocity(self):
        """
        Test moving the AWG with velocity.
        """
        # Move X (Channel 1) from 10 to 20 microns at 5 microns/second
        self.atto_scanner.MoveWithVelocity(channel=1, start_position=10.0, end_position=20.0, velocity=5.0)
        voltage_x = self.atto_scanner.get_current_voltage(channel=1)
        expected_voltage_x = 20.0 / 40.0  # End position
        self.assertAlmostEqual(voltage_x, expected_voltage_x, places=2, msg=f"X-axis movement error: {voltage_x} != {expected_voltage_x}")

    def test_move_to_points(self):
        """
        Test moving the AWG to a list of points.
        """
        points = [10, 20, 30, 40]  # Points in microns
        self.atto_scanner.MoveToPoints(channel=1, points=points)

        # Check that the waveform was written correctly by triggering the AWG and verifying each point
        for point in points:
            self.atto_scanner.awg.trigger()
            voltage_x = self.atto_scanner.get_current_voltage(channel=1)
            expected_voltage = point / 40.0
            self.assertAlmostEqual(voltage_x, expected_voltage, places=2, msg=f"Point error: {voltage_x} != {expected_voltage}")

    def test_set_velocity(self):
        """
        Test setting the velocity.
        """
        velocity = 10.0  # 10 microns/second
        self.atto_scanner.SetVelocity(channel=1, velocity=velocity)
        # No direct measurement possible for velocity, so simply check the output of the method (print statements)
        # or extend the method to save velocity for comparison.

if __name__ == "__main__":
    unittest.main()
