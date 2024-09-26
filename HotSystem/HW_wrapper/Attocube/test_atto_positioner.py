import unittest
from ..Attocube import AttoDry800


class TestAttoDry800(unittest.TestCase):
    def __init__(self, method_name: str = "runTest"):
        super().__init__(method_name)
        self.position_tolerance = 2000

    def setUp(self):
        """
        Set up a simulation and real device instances for testing.
        """
        # Initialize the device in both simulation and real modes
        self.device_sim = AttoDry800(address='192.168.101.53', simulation=True)
        self.device_real = AttoDry800(address='192.168.101.53', simulation=False)

    def test_connect(self):
        """
        Test device connection.
        """
        # Test the connection in simulation mode
        self.device_sim.connect(verbose=True)
        self.assertTrue(self.device_sim.is_connected(), "Device should be connected in simulation mode")

        # Test the connection in real mode
        self.device_real.connect(verbose=True)
        self.assertTrue(self.device_real.is_connected(), "Device should be connected in real mode")

    def test_disconnect(self):
        """
        Test device disconnection.
        """
        # Disconnect in simulation mode
        self.device_sim.disconnect(verbose=True)
        self.assertFalse(self.device_sim.is_connected(), "Device should be disconnected in simulation mode")

        # Disconnect in real mode
        self.device_real.disconnect(verbose=True)
        self.assertFalse(self.device_real.is_connected(), "Device should be disconnected in real mode")

    # def test_move_to_home(self):
    #     """
    #     Test moving a channel to its home position.
    #     """
    #     for channel in self.device_sim.channels:
    #         # Move to home in simulation mode
    #         self.device_sim.move_to_home(channel, verbose=True)
    #
    #         # Move to home in real mode
    #         self.device_real.connect()
    #         self.device_real.move_to_home(channel, verbose=True)

    def test_move_absolute(self):
        """
        Test moving a channel to an absolute position.
        """
        for channel in self.device_sim.channels:
            # Test in simulation mode
            initial_position = self.device_sim.get_position(channel, verbose=True)
            target_position = int(initial_position)  # Target position in nm or µ°
            self.device_sim.move_absolute(channel, target_position, verbose=True)
            final_position = self.device_sim.get_position(channel, verbose=True)
            self.assertAlmostEqual(final_position, target_position, delta=self.position_tolerance,
                                   msg=f"Simulation mode: Expected position {target_position} within "
                                       f"{self.position_tolerance} nm of {final_position}.")

            # Test in real mode
            self.device_real.connect()
            initial_position = self.device_real.get_position(channel, verbose=True)
            target_position = int(initial_position + 10000)  # Target position in nm or µ°
            self.device_real.move_absolute(channel, target_position, verbose=True)
            self.device_real.wait_for_axes_to_stop(channel, verbose=True)
            final_position = self.device_real.get_position(channel, verbose=True)
            self.assertAlmostEqual(final_position, target_position, delta=self.position_tolerance,
                                   msg=f"Real mode: Expected position {target_position} within "
                                       f"{self.position_tolerance} nm of {final_position}.")

    # noinspection DuplicatedCode
    def test_move_relative(self):
        """
        Test moving a channel by a relative number of steps.
        """
        for channel in self.device_sim.channels:
            # Test in simulation mode
            initial_position = self.device_sim.get_position(channel, verbose=True)
            steps = 0  # Steps in nm or µ°
            self.device_sim.move_relative(channel, steps, verbose=True)
            final_position = self.device_sim.get_position(channel, verbose=True)
            expected_position = initial_position + steps
            self.assertAlmostEqual(final_position, expected_position, delta=self.position_tolerance,
                                   msg=f"Simulation mode: Expected position {expected_position} within "
                                       f"{self.position_tolerance} nm of {final_position}.")

            # Test in real mode
            self.device_real.connect()
            initial_position = self.device_real.get_position(channel, verbose=True)
            steps = 10000  # Steps in nm or µ°
            self.device_real.move_relative(channel, steps, verbose=True)
            self.device_real.wait_for_axes_to_stop(channel, verbose=True)
            final_position = self.device_real.get_position(channel, verbose=True)
            expected_position = initial_position + steps
            self.assertAlmostEqual(final_position, expected_position, delta=self.position_tolerance,
                                   msg=f"Real mode: Expected position {expected_position} within "
                                       f"{self.position_tolerance} nm of {final_position}.")

    def test_check_and_enable_output(self):
        """
        Test enabling output for a channel.
        """
        for channel in self.device_sim.channels:
            # Check and enable output in simulation mode
            self.device_sim._check_and_enable_output(channel, verbose=True)

            # Check and enable output in real mode
            self.device_real.connect()
            self.device_real._check_and_enable_output(channel, verbose=True)

    def test_get_position(self):
        """
        Test getting the position of a specific axis.
        """
        for axis in self.device_sim.channels:
            # Get position in simulation mode
            position_sim = self.device_sim.get_position(axis, verbose=True)
            self.assertIsInstance(position_sim, float, "Position should be a float in simulation mode")

            # Get position in real mode
            self.device_real.connect()
            position_real = self.device_real.get_position(axis, verbose=True)
            self.assertIsInstance(position_real, float, "Position should be a float in real mode")

    def test_get_firmware_version(self):
        """
        Test getting the firmware version of the device.
        """
        # Get firmware version in simulation mode
        firmware_sim = self.device_sim.get_firmware_version(verbose=True)
        self.assertIsInstance(firmware_sim, str, "Firmware version should be a string in simulation mode")

        # Get firmware version in real mode
        self.device_real.connect()
        firmware_real = self.device_real.get_firmware_version(verbose=True)
        self.assertIsInstance(firmware_real, str, "Firmware version should be a string in real mode")

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.device_sim.disconnect()
        self.device_real.disconnect()


if __name__ == '__main__':
    unittest.main()
