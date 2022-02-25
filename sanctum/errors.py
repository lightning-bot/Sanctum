class NotFound(Exception):
    def __init__(self, thing: str, *, message: str = None):
        self.thing = thing
        # This is a custom message that will override
        self.message = None
