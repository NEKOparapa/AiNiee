"""Small shared initializer; business services have no event bus or global state."""


class Base:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not hasattr(self, "default"):
            self.default = {}
