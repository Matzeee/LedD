from ledd.effects.generatoreffect import GeneratorEffect
import spectra


class FadeEffect(GeneratorEffect):
    author = "LeDD-Freaks"
    version = "0.1"

    name = "Fade Effect"
    description = "Fades through the HSV color wheel"

    def execute(self):
        scale = spectra.scale([spectra.hsv(0.0, 1.0, 1.0), spectra.hsv(360, 1.0, 1.0)]).domain([0, 20000])

        i = 0
        while True:
            yield scale(i)
            i = (i + 1) % 20000
