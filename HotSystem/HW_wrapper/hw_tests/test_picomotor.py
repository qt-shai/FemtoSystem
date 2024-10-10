import unittest
from typing import Optional, List, Tuple
from HW_wrapper import newportPicomotor


class TestNewportPicomotor(unittest.TestCase):
    """
    Test cases for the `newportPicomotor` class.

    This test suite performs integration tests with the Newport Picomotor device.
    The tests assume the device is connected and accessible.

    Each test case validates communication, movement, and status retrieval
    functionalities of the Picomotor.
    """

    def setUp(self) -> None:
        """
        Set up the testing environment by initializing the `newportPicomotor` instance
        and connecting to the device if available.
        """
        # Create an instance of newportPicomotor
        self.picomotor = newportPicomotor(simulation=False)

        # Connect to the device
        self.picomotor.connect()

        # Check if the device is connected before proceeding
        if not self.picomotor.IsConnected:
            self.skipTest("Device is not connected. Skipping tests.")

    def tearDown(self) -> None:
        """
        Clean up by disconnecting from the device after each test case.
        """
        self.picomotor.Disconnect()

    def test_connection(self) -> None:
        """
        Test the connection to the Picomotor device.

        The test verifies that the device is connected and the basic properties
        like device address and model information are correctly retrieved.
        """
        self.assertTrue(self.picomotor.IsConnected, "Device should be connected.")
        device_address: str = self.picomotor.GetDeviceAddress()
        self.assertIsInstance(device_address, str, "Device address should be a string.")
        self.assertNotEqual(device_address, "", "Device address should not be empty.")

    def test_get_device_address(self) -> None:
        """
        Test getting the device address.

        This test retrieves the device address and ensures it is a valid IP address
        or identifier of the device.
        """
        device_address: str = self.picomotor.GetDeviceAddress()
        self.assertIsInstance(device_address, str)
        self.assertNotEqual(device_address, "", "Device address should not be empty.")

    def test_get_position(self) -> None:
        """
        Test getting the current position of all channels.

        The test retrieves positions for all channels and validates that the positions
        are within expected ranges.
        """
        self.picomotor.GetPosition()
        positions: List[int] = self.picomotor.AxesPositions
        for pos in positions:
            self.assertIsInstance(pos, int, "Position should be an integer value.")
            self.assertGreaterEqual(pos, 0, "Position should be non-negative.")

    def test_move_relative(self) -> None:
        """
        Test performing a relative move on a motor.

        This test moves motor 1 by 100 steps and verifies the final position
        by reading back the position after movement.
        """
        initial_position: Tuple[Optional[int], str] = self.picomotor.ReadPosition(1)
        self.assertIsNotNone(initial_position[0], "Initial position should not be None.")
        initial_pos_value: int = initial_position[0]

        # Perform a relative move of 100 steps on motor 1
        self.picomotor.MoveRelative(1, 100)

        # Get the new position
        new_position: Tuple[Optional[int], str] = self.picomotor.ReadPosition(1)
        self.assertIsNotNone(new_position[0], "New position should not be None.")
        self.assertEqual(new_position[0], initial_pos_value + 100, "Position should have increased by 100 steps.")

    def test_move_absolute(self) -> None:
        """
        Test performing an absolute move on a motor.

        This test moves motor 1 to an absolute position of 5000 steps and verifies
        the position by reading it back.
        """
        # Move motor 1 to position 5000
        self.picomotor.MoveABSOLUTE(1, 5000)

        # Read back the position
        position: Tuple[Optional[int], str] = self.picomotor.ReadPosition(1)
        self.assertIsNotNone(position[0], "Position should not be None.")
        self.assertEqual(position[0], 5000, "Motor position should be 5000 steps.")

    def test_velocity_and_acceleration(self) -> None:
        """
        Test setting and getting velocity and acceleration.

        This test sets the velocity and acceleration values for motor 1 and validates
        that the values are set correctly.
        """
        # Set velocity to 1500 steps/sec
        self.picomotor.SetVelocity(1, 1500)
        self.picomotor.GetVelocities()
        self.assertEqual(self.picomotor.AxesVelocities[0], 1500, "Velocity should be 1500 steps/sec.")

        # Set acceleration to 10000 steps/sec^2
        self.picomotor.SetAcceleration(1, 10000)
        self.picomotor.GetAcceleration()
        self.assertEqual(self.picomotor.AxesAcceleraitions[0], 10000, "Acceleration should be 10000 steps/sec^2.")

    def test_stop_motion(self) -> None:
        """
        Test stopping motion on the specified motor.

        This test initiates a relative move and then stops it, ensuring the motor
        stops as expected.
        """
        # Move the motor and then stop
        self.picomotor.MoveRelative(1, 500)
        self.picomotor.StopMotion(1)

        # Read the motion done status
        motion_done: bool = self.picomotor.GetMotionDone(1)
        self.assertTrue(motion_done, "Motion should be completed or stopped successfully.")

    def test_get_motor_type(self) -> None:
        """
        Test retrieving the motor type of a specified motor.

        This test retrieves and validates the motor type for motor 1.
        """
        motor_type: Optional[str] = self.picomotor.GetMotorType(1)
        self.assertIsInstance(motor_type, str, "Motor type should be a string value.")
        self.assertNotEqual(motor_type, "", "Motor type should not be an empty string.")


if __name__ == '__main__':
    unittest.main()
