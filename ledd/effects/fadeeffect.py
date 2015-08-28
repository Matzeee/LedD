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

import spectra

from ledd.effects.generatoreffect import GeneratorEffect


class FadeEffect(GeneratorEffect):
    author = "LeDD-Freaks"
    version = "0.1"

    name = "Fade Effect"
    description = "Fades through the HSV color wheel"

    def execute(self):
        scale = spectra.scale([spectra.hsv(0.0, 1.0, 1.0), spectra.hsv(360.0, 1.0, 1.0)]).domain([0, 20000])

        i = 0
        while True:
            yield scale(i)
            i = (i + 1) % 20000
