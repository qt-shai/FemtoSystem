class EventDispatcher:
    def __init__(self, event):
        self._event = event

    def dispatch(self, func):
        # event_class_name = self._event.__class__.__name__
        # func._event_type = event_class_name
        # if isinstance(self._event, type(func._event_type)):
        if self._event._event_type == func._event_type:
            self._event.handled = func(self._event)
            self.handled = True
            return True
        return False