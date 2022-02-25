class NotFound(Exception):
    def __init__(self, thing: str = None, *, message: str = None):
        self.thing = thing
        # This is a custom message that will override
        self.message = message
