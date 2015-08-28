import asyncio

from ledd.effects.fadeeffect import FadeEffect


class EffectStack(object):
    def __init__(self):
        self.stripes = []
        self.effect = FadeEffect()
        # TODO
        self.modifiers = []

    def start(self):
        asyncio.get_event_loop().call_soon(self.execute)

    def execute(self):
        color = self.effect.execute_internal()

        for stripe in self.stripes:
            stripe.set_color(color)

        # schedule next execution
        asyncio.get_event_loop().call_later(0.1, self.execute)
