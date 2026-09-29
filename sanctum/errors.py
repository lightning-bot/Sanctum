from typing import Union


class NotFound(Exception):
    def __init__(self, thing: Union[str, None] = None,
                 *, message: Union[str, None] = None):
        self.thing = thing
        # This is a custom message that will override
        self.message = message
