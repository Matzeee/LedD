# LEDD Project
# Copyright (C) 2015 LEDD Team
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
