import time

class MockJob:
    """
    A mock QmJob-like class for testing 'fetching_tool' or other host-side
    code without a real OPX / QmJob.
    This pretty much only tests if the fetching tool,fetch and GlobalFetch functions work and speak to each other
    If stream processing is needed and/or it is interesting to see how stuff defined in qua works,
    please define a quantum machine
    """
    def __init__(self, simulated_streams=None, update_interval=0.5):
        """
        :param simulated_streams: dict {stream_name: list of data points}
        :param update_interval: time in seconds between new data arrivals (simulates streaming)
        """
        self.is_running = True
        self.update_interval = update_interval
        self._start_time = time.time()

        # Provide the new default streams if none are provided
        if simulated_streams is None:
            simulated_streams = {
                "iteration_list":      [0, 1, 2, 3, 4],
                "times":               [10, 12, 15, 20, 25],  # example times
                "counts":              [5, 7, 9, 14, 15],
                "statistics_counts":   [2, 2, 3, 4, 5],
            }

        self._result_handles = MockResultHandles(simulated_streams, update_interval)

    @property
    def result_handles(self):
        return self._result_handles

    def halt(self):
        print("MockJob halted.")
        self.is_running = False

    def pause(self):
        print("MockJob paused.")
        self.is_running = False

    def resume(self):
        print("MockJob resumed.")
        self.is_running = True


class MockResultHandles:
    """
    Simulates the 'result_handles' object of a real QmJob.
    Provides attributes for each stream name, plus:
      - is_processing()
      - wait_for_all_values()
      - get(stream_name)
    """
    def __init__(self, simulated_streams, update_interval):
        self._start_time = time.time()
        self._update_interval = update_interval

        # We'll keep a dictionary of {stream_name: <MockStream object>}
        self._streams = {}
        for name, data_list in simulated_streams.items():
            self._streams[name] = MockStream(name, data_list, update_interval)

    def is_processing(self):
        for stream in self._streams.values():
            if not stream.is_fully_released():
                return True
        return False

    def wait_for_all_values(self):
        for stream in self._streams.values():
            stream.release_all()

    def get(self, stream_name):
        if stream_name not in self._streams:
            raise KeyError(f"Stream '{stream_name}' not found in mock.")
        return self._streams[stream_name]

    def __getattr__(self, name):
        """
        For statements like 'hasattr(self.res_handles, "times")'
        or 'self.res_handles.times' in the code, we interpret them
        as checking streams.
        """
        if name in self._streams:
            return self._streams[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class MockStream:
    """
    Simulates a single stream handle, e.g. what you get with:
    job.result_handles.get("times")
    Must support:
      - .fetch_all()
      - .wait_for_values(num_points)
      - (optionally) partial release over time
    """
    def __init__(self, stream_name, data_list, update_interval):
        self.stream_name = stream_name
        self.full_data = data_list
        self._released_index = 0
        self.update_interval = update_interval
        self._start_time = time.time()

    def fetch_all(self):
        """
        Returns all data points that have been released so far.
        """
        self._update_released_index()
        return self.full_data[: self._released_index]

    def wait_for_values(self, num_values):
        """
        A convenience used by 'fetching_tool' in 'live' mode:
        Wait until at least 'num_values' points are released (or all if fewer remain).
        """
        while True:
            self._update_released_index()
            if (self._released_index >= num_values) or (self._released_index >= len(self.full_data)):
                break
            time.sleep(0.05)  # short sleep simulating incremental release

    def is_fully_released(self):
        """True if we've released all data in 'full_data'."""
        self._update_released_index()
        return self._released_index >= len(self.full_data)

    def release_all(self):
        """For wait_for_all_values(), release everything at once."""
        self._released_index = len(self.full_data)

    def _update_released_index(self):
        """
        Simulate partial release over time. Every 'update_interval' seconds, we release 1 new data point.
        Adjust logic as needed for your use case.
        """
        elapsed = time.time() - self._start_time
        intervals_passed = int(elapsed // self.update_interval)
        self._released_index = min(len(self.full_data), intervals_passed)
