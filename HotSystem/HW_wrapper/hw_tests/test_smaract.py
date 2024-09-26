import unittest
from HW_wrapper import smaractMCS2


class TestSmaractMCS2(unittest.TestCase):

    def test_connect_to_specific_device(self):
        """
        Test connecting to a specific device when more than one SmarAct device is available.
        This test uses actual hardware and verifies the serial number of the connected device.
        """
        # Instantiate smaractMCS2 class
        smaract = smaractMCS2()

        # Get the available devices
        devices = smaract.get_available_devices()

        # Verify that there is more than one device available
        self.assertGreater(len(devices), 1, "Expected more than one SmarAct device to be available")

        # Choose a specific device to connect to by serial number (e.g., second device)
        target_device = devices[0].serial_number

        # Attempt to connect to the selected device
        smaract.connect(f'network:sn:{target_device}')

        # Verify that the connected device's serial number matches the expected one
        self.assertTrue(smaract.IsConnected, "Device failed to connect")
        self.assertEqual(smaract.devSerial, target_device,
                         f"Connected to the wrong device. Expected: {target_device}, got: {smaract.devSerial}")

    def test_no_devices_available(self):
        """
        Test the scenario where no devices are available.
        This test verifies that the system handles no available devices correctly.
        """
        # Instantiate smaractMCS2 class
        smaract = smaractMCS2()

        # Get the available devices
        devices = smaract.get_available_devices()

        # Verify that there are no devices available
        self.assertEqual(len(devices), 0, "Expected no devices to be available")

    def test_device_connection_and_disconnection(self):
        """
        Test connecting to and disconnecting from a SmarAct device.
        This test uses actual hardware and verifies connection and disconnection behavior.
        """
        # Instantiate smaractMCS2 class
        smaract = smaractMCS2()

        # Get the available devices
        devices = smaract.get_available_devices()

        # Verify that at least one device is available
        self.assertGreater(len(devices), 0, "No SmarAct devices available for testing")

        # Attempt to connect to the first available device
        smaract.connect(f'network:sn:{devices[0].serial_number}')

        # Verify the device is connected
        self.assertTrue(smaract.IsConnected, "Failed to connect to SmarAct device")

        # Now disconnect from the device
        smaract.Disconnect()

        # Verify the device is disconnected
        self.assertFalse(smaract.IsConnected, "Failed to disconnect from SmarAct device")


if __name__ == '__main__':
    unittest.main()
