import threading
import asyncio
from datetime import datetime
import time

import dearpygui.dearpygui as dpg

def run_asyncio_loop(loop):
    """Helper function to run an asyncio loop in a separate thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()

class GUISIM960:
    def __init__(self, sim960):
        self.dev = sim960
        self.simulation = False  # Example; adapt to your usage
        self.continuous_read_active = False

        # --- 1) Create the background asyncio loop ---
        self.background_loop = asyncio.new_event_loop()

        # --- 2) Start the loop in a separate thread ---
        t = threading.Thread(
            target=run_asyncio_loop,
            args=(self.background_loop,),
            daemon=True
        )
        t.start()

        # Example main window
        with dpg.window(label="SRS SIM960 Example", width=600, height=200):
            dpg.add_button(label="Start/Stop Continuous Read", callback=self.cb_toggle_continuous_read)

    def cb_toggle_continuous_read(self):
        """
        Toggle the continuous reading of measurement.
        """
        if not self.continuous_read_active:
            self.continuous_read_active = True
            print("Starting continuous read...")
            # Schedule our asynchronous read task on the event loop
            self.background_loop.create_task(self._continuous_read_task())
        else:
            print("Stopping continuous read...")
            self.continuous_read_active = False

    async def _continuous_read_task(self):
        """
        Continuously reads the device measurement once per second and prints the result.
        """
        while self.continuous_read_active:
            # In real code, check for self.simulation or device read:
            if not self.simulation:
                value = self.dev.read_measure_input()
                print(f"[{datetime.now()}] Measurement = {value:.4f}")
            else:
                # If you have a simulation mode, read or mock a reading
                print(f"[{datetime.now()}] Simulation measurement = 42.0000")

            # Sleep for 1 second in the asyncio world
            await asyncio.sleep(1.0)

    def show(self):
        """
        Show the window; afterwards call dpg.start_dearpygui() to start the event loop.
        """
        # Just an example of how to show an item if it were hidden.
        # If you constructed the window inline, you may not need this.
        pass

# Usage (minimal demo):
# sim_device = SRSsim960(...)  # your actual device
# gui = GUISIM960(sim_device)
# gui.show()
# dpg.start_dearpygui()
