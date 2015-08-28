
from ledd.effects.baseeffect import BaseEffect
from spectra import Color


class GeneratorEffect(BaseEffect):
    """
    This is a base class for simple effects.
    It should yield a new color on each execution.
    """

    def __init__(self):
        """
        Do not override, use setup instead.
        """
        self.generator = self.execute()

    def setup(self):
        pass

    def execute_internal(self):
        c = next(self.generator)
        assert isinstance(c, Color)
        return c

    def execute(self):
        pass

    def tear_down(self):
        pass
