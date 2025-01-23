import numpy as np

class MockJob():
    def __init__(self, counts):
        self.results = {"counts": counts}  # Mock results
        self.result_handles = MockResultHandles(self.results)

    # def result_handles(self):
    #     return MockResultHandles(self.results)

class MockResultHandles:
    def __init__(self, results):
        self.results = results
        self.counts = 'counts'

    def get(self, key):
        # Return mock data for a specific key
        return self.results[key]
