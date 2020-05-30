from photons_canvas import point_helpers as php
from photons_canvas.animations import options

from delfick_project.norms import dictobj, sb
import math


def clamp(val, mn=0, mx=1):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    return val


class LineOptions(dictobj.Spec):
    rate = dictobj.Field(options.rate_spec((0.2, 0.4)))
    line_hues = dictobj.Field(options.color_range_spec("rainbow"))
    fade_amount = dictobj.Field(sb.float_spec, default=0.1)
    line_tip_hues = dictobj.NullableField(options.color_range_spec(None))

    def make_line(self, length):
        color1 = self.line_hues.color

        color2 = None
        if self.line_tip_hues is not None:
            color2 = self.line_tip_hues.color

        return Line(length, color1, color2)


class Line:
    def __init__(self, length, color1, color2=None):
        self.color1 = color1
        self.color2 = color2
        self.length = length
        self.tip = []
        self.body_pixels = [color1 for _ in range(length)]
        self.position = 0

    def progress(self, rate):
        self.position += rate

        if self.color2 is None:
            self.progress_one_color()
        else:
            self.progress_two_colors()

    def pixels(self, start, reverse=False, tail=None):
        start = start + math.floor(self.position)

        pixels = self.body_pixels + self.tip
        if reverse:
            pixels = reversed(pixels)

        for _ in range(tail or 0):
            yield start, None
            start += 1

        for pixel in pixels:
            yield start, pixel
            start += 1

    def progress_one_color(self):
        position = self.position
        brightness = clamp(1 - (position - math.floor(position)))
        if brightness <= 0:
            self.tip = []
        else:
            self.tip = [php.Color.adjust(self.color1, brightness_change=(brightness,))]

    def progress_two_colors(self):
        position = self.position
        closeness = clamp(1.0 - (position - math.floor(position)))

        head_color = php.Color.adjust(self.color1, brightness_change=(closeness,))

        middle_color = php.Color.adjust(
            self.color1, hue_change=min([10, (self.color2.hue - self.color1.hue) * closeness])
        )

        self.tip = [head_color, middle_color, self.color2]
