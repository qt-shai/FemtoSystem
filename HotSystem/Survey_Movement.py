""" This Document Moves a motor to a desired position.
    The data is passed from Survey_Get_Data class"""

"""This file should also include the functions for performing experiments.
Start with get_max_peak_intensity and then call one of the Experiment function 
from the OPX."""
import time

class Survey_Move_To_Position:
    def __init__(self, move_function, get_position_function):
        self.move_function = move_function
        self.get_position_function = get_position_function
        self.position = None

    def move_to_position(self, channel: int, position) -> bool:
        try:
            position_int = int(round(position))
            if channel is not None:
                #Based on the atto_positioner requirements for input
                self.move_function(channel, position_int)
            else:
                # Check how other motors move and update accordingly
                self.move_function(position_int)
            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"Error moving motor on channel {channel} to position {position}: {e}")
            return False

    def move_to_positions(self, positions) -> bool:
        # Build for future usages with multiple data points, but not currently tested
        # Change this not to attempt other moves if one failed?
        success = True
        for channel, target in positions.items():
            if not self.move_to_position(channel, target):
                success = False
                # Continue attempting other moves even if one fails.
        return success

    def perform_experiment(self, experiment_type):
        pass