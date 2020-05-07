from photons_canvas.animations import options
from photons_canvas import CanvasColor

from delfick_project.norms import dictobj, Meta, sb
import random
import math


def clamp(val, mn=0, mx=1):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    return val


class LineOptions(dictobj.Spec):
    line_hues = dictobj.NullableField(
        options.split_by_comma(options.hue_range_spec()), wrapper=sb.optional_spec
    )
    fade_amount = dictobj.Field(sb.float_spec, default=0.1)
    line_tip_hues = dictobj.NullableField(
        options.split_by_comma(options.hue_range_spec()), wrapper=sb.optional_spec
    )

    min_speed = dictobj.Field(sb.float_spec, default=0.2)
    max_speed = dictobj.Field(sb.float_spec, default=0.4)

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)

        options.normalise_speed_options(self)

        if self.line_hues == []:
            self.line_hues = None

        if self.line_tip_hues == []:
            self.line_tip_hues = None

        if self.line_hues is sb.NotSpecified:
            self.line_hues = [options.hue_range_spec().normalise(Meta.empty(), "rainbow")]

        if self.line_tip_hues is sb.NotSpecified:
            self.line_tip_hues = None

    def make_rate(self):
        if self.min_speed == self.max_speed:
            return self.min_speed

        mn = int(self.min_speed * 100)
        mx = int(self.max_speed * 100)
        return random.randint(mn, mx) / 100

    def make_line(self, length):
        color1 = CanvasColor(random.choice(self.line_hues).make_hue(), 1, 1, 3500)

        color2 = None
        if self.line_tip_hues is not None:
            color2 = CanvasColor(random.choice(self.line_tip_hues).make_hue(), 1, 1, 3500)

        return Line(length, color1, color2)


class Line:
    def __init__(self, length, color1, color2=None):
        self.color1 = color1
        self.color2 = color2
        self.length = length
        self.tip = []
        self.body_pixels = [color1.clone() for _ in range(length)]
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
            self.tip = [self.color1.clone()]
            self.tip[0].brightness = brightness

    def progress_two_colors(self):
        position = self.position
        closeness = clamp(1.0 - (position - math.floor(position)))

        head_color = self.color1.clone()
        head_color.brightness = closeness

        middle_color = self.color1.clone()
        middle_color.hue = self.color1.hue + min(
            [10, (self.color2.hue - self.color1.hue) * closeness]
        )
        while middle_color.hue > 360:
            middle_color.hue -= 360

        self.tip = [head_color, middle_color, self.color2.clone()]
