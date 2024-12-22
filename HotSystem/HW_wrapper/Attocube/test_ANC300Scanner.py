import unittest
import time

from HW_wrapper.Attocube import ANC300Modes, Anc300Wrapper


class TestAnc300Wrapper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Try connecting to the device. If not present, skip tests.
        cls.conn = "192.168.101.20"  # Example connection, update to actual device IP and port if needed.
        cls.wrapper = Anc300Wrapper(conn=cls.conn, simulation=False)
        try:
            cls.wrapper.connect()
            if not cls.wrapper.is_connected:
                raise RuntimeError("Device not connected.")
        except Exception as e:
            print(f"Skipping tests because device is not available: {e}")
            cls.wrapper = None

    @classmethod
    def tearDownClass(cls):
        if cls.wrapper and cls.wrapper.is_connected:
            cls.wrapper.disconnect()

    def setUp(self):
        time.sleep(0.1)
        if self.wrapper is None:
            self.skipTest("Device not available, skipping test.")
        # Ensure device is in a known good state at the start of each test.
        for ch in self.wrapper.channels:
            self.wrapper.set_offset_voltage(ch, 0)
            self.wrapper.set_mode(ch, ANC300Modes.GND)

    def test_connection(self):
        self.assertTrue(self.wrapper.is_connected, "Device should be connected")

    def test_channels(self):
        # Verify we have the expected channels.
        self.assertListEqual(self.wrapper.channels, [1, 2], "Expected channels are [1,2]")

    def test_offset_voltage_set_get_valid(self):
        # Set within limit and verify
        test_voltage = 10.0
        for ch in self.wrapper.channels:
            self.wrapper.set_offset_voltage(ch, test_voltage)
            read_voltage = self.wrapper.get_offset_voltage(ch)
            self.assertAlmostEqual(read_voltage, test_voltage, places=1, msg="Offset voltage not set correctly")

    def test_offset_voltage_limit(self):
        # Attempt to set above 59V should raise ValueError
        with self.assertRaises(ValueError):
            self.wrapper.set_offset_voltage(self.wrapper.channels[0], 60.0)

    def test_offset_voltage_invalid_channel(self):
        # Try invalid channel
        with self.assertRaises(ValueError):
            self.wrapper.set_offset_voltage(999, 10.0)

    def test_move_absolute_within_range(self):
        # Move to half of max travel
        half_travel = self.wrapper.max_travel / 4
        ch = self.wrapper.channels[0]
        self.wrapper.set_mode(ch, ANC300Modes.OFFSET)
        self.wrapper.MoveABSOLUTE(ch, half_travel)
        time.sleep(1)
        pos = self.wrapper.get_position(ch)
        self.wrapper.set_mode(ch, ANC300Modes.GND)
        # Position should be close to half_travel
        self.assertAlmostEqual(pos, half_travel, delta=half_travel*0.2, msg="Position not within expected range")

    def test_move_absolute_exceed_range(self):
        # Attempt to move beyond max travel should clip at 59V
        # MoveABSOLUTE converts position to a voltage, we test behavior by setting a very large position
        ch = self.wrapper.channels[0]
        large_position = self.wrapper.max_travel * 10  # artificially large
        with self.assertRaises(ValueError):
            self.wrapper.MoveABSOLUTE(ch, large_position)


    def test_move_relative(self):
        ch = self.wrapper.channels[0]
        initial_pos = self.wrapper.get_position(ch)
        steps = 5  # move 5 microns
        self.wrapper.set_mode(ch, ANC300Modes.OFFSET)
        self.wrapper.move_relative(ch, steps)
        time.sleep(1)
        pos = self.wrapper.get_position(ch)
        self.wrapper.set_mode(ch, ANC300Modes.GND)
        self.assertGreaterEqual(pos, initial_pos, "Relative move did not move forward as expected")

    # def test_move_to_home(self):
    #     ch = self.wrapper.channels[0]
    #     # Move somewhere else first
    #     self.wrapper.MoveABSOLUTE(ch, self.wrapper.max_travel / 2)
    #     self.wrapper.move_to_home(ch)
    #     pos = self.wrapper.get_position(ch)
    #     # Home is zero position, allow some tolerance
    #     self.assertAlmostEqual(pos, 0.0, delta=1e-6, msg="Failed to move back to home")

    def test_stop_all_axes(self):
        # There's no direct method to test is_moving aside from device.is_moving,
        # but we can at least run stop and ensure no exceptions
        self.wrapper.stop_all_axes()

    def test_status_and_inpos(self):
        ch = self.wrapper.channels[0]
        # Move absolute and check status. The actual motion might be too quick to catch "Moving", but we try.
        self.wrapper.MoveABSOLUTE(ch, self.wrapper.max_travel / 4)
        status = self.wrapper.get_status(ch)
        self.assertIn(status, ["Moving", "Idle"], "Status should be either 'Moving' or 'Idle'")
        inpos = self.wrapper.readInpos(ch)
        self.assertIsInstance(inpos, bool, "readInpos should return a boolean")

    def test_modes(self):
        ch = self.wrapper.channels[0]
        # Set a mode and read it back
        self.wrapper.set_mode(ch, ANC300Modes.OFFSET)
        mode = self.wrapper.get_mode(ch)
        self.assertEqual(mode, ANC300Modes.OFFSET, "Mode not set or read correctly")

        # Test an unsupported scenario (e.g., setting mode to stp on a module that doesn't support it)
        # This depends on actual hardware configuration, but we at least try setting different modes.
        self.wrapper.set_mode(ch, ANC300Modes.STP_PLUS)
        mode = self.wrapper.get_mode(ch)
        # If the hardware doesn't support it, it might fail or return a fallback, but we at least check no exception is raised.

        self.wrapper.set_mode(ch, ANC300Modes.GND)
        mode = self.wrapper.get_mode(ch)
        self.assertEqual(mode, ANC300Modes.GND, "Mode not set or read correctly")

    def test_external_input_modes(self):
        ch = self.wrapper.channels[0]
        # Enable DC input and check
        self.wrapper.set_external_input_modes(ch, dcin=True, acin=False)
        dcin, acin = self.wrapper.get_external_input_modes(ch)
        self.assertTrue(dcin, "DC input mode should be enabled")
        self.assertFalse(acin, "AC input mode should be disabled")

        # Enable AC input and check
        self.wrapper.set_external_input_modes(ch, dcin=False, acin=True)
        dcin, acin = self.wrapper.get_external_input_modes(ch)
        self.assertFalse(dcin, "DC input mode should be disabled now")
        self.assertTrue(acin, "AC input mode should be enabled now")

        self.wrapper.set_external_input_modes(ch, dcin=False, acin=False)
        dcin, acin = self.wrapper.get_external_input_modes(ch)
        self.assertFalse(dcin, "DC input mode should be disabled now")
        self.assertFalse(acin, "AC input mode should be enabled now")


    # def test_set_zero_position(self):
    #     ch = self.wrapper.channels[0]
    #     # Move somewhere
    #     self.wrapper.MoveABSOLUTE(ch, self.wrapper.max_travel / 3)
    #     # Set zero
    #     self.wrapper.set_zero_position(ch)
    #     # Position should be considered zero now internally
    #     pos = self.wrapper.AxesPositions[self.wrapper.channels.index(ch)]
    #     self.assertAlmostEqual(pos, 0.0, delta=1e-6, msg="Axis position not reset to zero internally")

    def test_disconnect(self):
        # Disconnecting after tests complete
        if self.wrapper.is_connected:
            self.wrapper.disconnect()
            self.assertFalse(self.wrapper.is_connected, "Wrapper should be disconnected now")


if __name__ == "__main__":
    unittest.main()
