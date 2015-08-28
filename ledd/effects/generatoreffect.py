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

from spectra import Color

from ledd.effects.baseeffect import BaseEffect


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
