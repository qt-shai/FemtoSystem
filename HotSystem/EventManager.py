import threading

class EventManager:
    def __init__(self):
        self.callbacks = {}

    def register_callback(self, event, callback):
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

    def trigger_event(self, event, *args, **kwargs):
        if event in self.callbacks:
            threads = [threading.Thread(target=callback, args=args, kwargs=kwargs) for callback in self.callbacks[event]]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()