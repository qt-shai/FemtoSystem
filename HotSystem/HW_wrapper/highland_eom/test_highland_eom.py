import unittest
from ..highland_eom import HighlandT130

# Flag to control whether to test the real device or only the simulation
TEST_REAL_DEVICE = True  # Set to True to test the real device


class TestHighlandT130(unittest.TestCase):

    def setUp(self):
        """
        Set up instances of the HighlandT130 device for testing.
        """
        # Initialize the device in both simulation and real modes based on the flag
        self.device_sim = HighlandT130(address='COM5', simulation=True)
        if TEST_REAL_DEVICE:
            self.device_real = HighlandT130(address='ASRL5::INSTR', simulation=False)

    def test_device_identity(self):
        """
        Test retrieving the device identity.
        """
        # Test in simulation mode
        response_sim = self.device_sim.get_device_identity(verbose=True)
        self.assertEqual(response_sim, "OK", "Simulation mode: Device identity retrieval failed.")

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            response_real = self.device_real.get_device_identity(verbose=True)
            self.assertIsNotNone(response_real, "Real mode: Failed to retrieve device identity.")
            print(f"Device Identity (Real): {response_real}")

    def test_device_status(self):
        """
        Test retrieving the device status.
        """
        # Test in simulation mode
        response_sim = self.device_sim.get_device_status(verbose=True)
        self.assertEqual(response_sim, "OK", "Simulation mode: Device status retrieval failed.")

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            response_real = self.device_real.get_device_status(verbose=True)
            self.assertIsNotNone(response_real, "Real mode: Failed to retrieve device status.")
            print(f"Device Status (Real): {response_real}")

    def test_set_range(self):
        """
        Test setting the timing range of the device.
        """
        # Test in simulation mode
        for range_value in [1, 2, 3]:
            self.device_sim.set_range(range_value, verbose=True)

        with self.assertRaises(ValueError):
            self.device_sim.set_range(5)

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            for range_value in [1, 2, 3]:
                self.device_real.set_range(range_value, verbose=True)

            with self.assertRaises(ValueError):
                self.device_real.set_range(5)

    def test_set_delay(self):
        """
        Test setting the delay of the output pulse.
        """
        delay_values = [0.5, 10.0, 100.0]  # Example delays in nanoseconds

        # Test in simulation mode
        for delay in delay_values:
            self.device_sim.set_delay(delay, verbose=True)

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            for delay in delay_values:
                self.device_real.set_delay(delay, verbose=True)

            with self.assertRaises(ValueError):
                self.device_real.set_delay(1000.5)
            with self.assertRaises(ValueError):
                self.device_real.set_delay(-0.5)

    def test_set_width(self):
        """
        Test setting the width of the output pulse.
        """
        width_values = [5.0, 50.0, 100.0]  # Example widths in nanoseconds

        # Test in simulation mode
        for width in width_values:
            self.device_sim.set_width(width, verbose=True)

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            for width in width_values:
                self.device_real.set_width(width, verbose=True)

            with self.assertRaises(ValueError):
                self.device_real.set_width(1000.5)
            with self.assertRaises(ValueError):
                self.device_real.set_width(0.5)

    def test_set_amplitude(self):
        """
        Test setting the output pulse amplitude.
        """
        amplitude_values = [0.25, 3, 7.2]  # Example amplitudes in volts

        # Test in simulation mode
        for amplitude in amplitude_values:
            self.device_sim.set_amplitude(amplitude, verbose=True)

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            for amplitude in amplitude_values:
                self.device_real.set_amplitude(amplitude, verbose=True)

            with self.assertRaises(ValueError):
                self.device_real.set_width(0.1)
            with self.assertRaises(ValueError):
                    self.device_real.set_width(7.3)

    def test_set_bias(self):
        """
        Test setting the bias voltage and source.
        """
        bias_values = [-5.9, 5.9, 0.0]  # Example bias voltages in volts

        # Test in simulation mode
        for bias in bias_values:
            self.device_sim.set_bias(bias, internal=True, verbose=True)
            self.device_sim.set_bias(bias, internal=False, verbose=True)

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            for bias in bias_values:
                self.device_real.set_bias(bias, internal=True, verbose=True)
                self.device_real.set_bias(bias, internal=False, verbose=True)

            with self.assertRaises(ValueError):
                self.device_real.set_bias(-6.5)
            with self.assertRaises(ValueError):
                self.device_real.set_bias(6.5)

    def test_get_error_status(self):
        """
        Test retrieving the error status of the device.
        """
        # Test in simulation mode
        response_sim = self.device_sim.get_error_status(verbose=True)
        self.assertEqual(response_sim, "OK", "Simulation mode: Error status retrieval failed.")

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            response_real = self.device_real.get_error_status(verbose=True)
            self.assertIsNotNone(response_real, "Real mode: Failed to retrieve error status.")
            print(f"Error Status (Real): {response_real}")

    def test_save_and_recall_configuration(self):
        """
        Test saving and recalling configurations on the device.
        """
        config_names = ["config1", "config2", "test_config"]

        # Test in simulation mode
        for name in config_names:
            self.device_sim.save_configuration(name, verbose=True)
            self.device_sim.recall_configuration(name, verbose=True)
        self.device_sim.recall_configuration(verbose=True)

        # # Test in real mode if enabled
        # if TEST_REAL_DEVICE:
        #     for name in config_names:
        #         self.device_real.save_configuration(name, verbose=True)
        #         self.device_real.recall_configuration(name, verbose=True)
        #     self.device_real.recall_configuration(verbose=True)

    def test_list_configurations(self):
        """
        Test listing all saved configurations on the device.
        """
        # Test in simulation mode
        response_sim = self.device_sim.list_configurations(verbose=True)
        self.assertEqual(response_sim, "OK", "Simulation mode: Listing configurations failed.")

        # Test in real mode if enabled
        if TEST_REAL_DEVICE:
            response_real = self.device_real.list_configurations(verbose=True)
            self.assertIsNotNone(response_real, "Real mode: Failed to list configurations.")
            print(f"Configurations (Real): {response_real}")

    def tearDown(self):
        """
        Clean up after each test.
        """
        self.device_real.close_connection()
        self.device_sim.close_connection()

if __name__ == '__main__':
    unittest.main()
