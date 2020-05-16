from photons_canvas.points.color import Color

import math

_Point = None


def Point(col, row):
    global _Point
    if _Point is None:
        _Point = __import__("photons_canvas.points.containers").points.containers.Point
    return _Point(col, row)


def hsbk(color):
    if color is None:
        return 0, 0, 0, 0
    elif isinstance(color, tuple):
        return color
    elif isinstance(color, Color):
        return tuple(color)

    if isinstance(color, dict):
        h = color["hue"]
        s = color["saturation"]
        b = color["brightness"]
        k = color["kelvin"]
    else:
        h = color.hue
        s = color.saturation
        b = color.brightness
        k = color.kelvin

    return h, s, b, k


def average_color(colors):
    colors = [c for c in colors if c is not None]

    if not colors:
        return None

    hue_x_total = 0
    hue_y_total = 0
    saturation_total = 0
    brightness_total = 0
    kelvin_total = 0

    for color in colors:
        if isinstance(color, tuple):
            h, s, b, k = color
        else:
            h = color.hue
            s = color.saturation
            b = color.brightness
            k = color.kelvin

        hue_x_total += math.sin(h * 2.0 * math.pi / 360)
        hue_y_total += math.cos(h * 2.0 * math.pi / 360)
        saturation_total += s
        brightness_total += b

        if k == 0:
            kelvin_total += 3500
        else:
            kelvin_total += k

    hue = math.atan2(hue_x_total, hue_y_total) / (2.0 * math.pi)
    if hue < 0.0:
        hue += 1.0
    hue *= 360

    number_colors = len(colors)
    saturation = saturation_total / number_colors
    brightness = brightness_total / number_colors
    kelvin = int(kelvin_total / number_colors)

    return (hue, saturation, brightness, kelvin)


class Points:
    @classmethod
    def cols(kls, bounds):
        (l, r), _, _ = bounds
        for col in range(l, r):
            yield kls.col(col, bounds)

    @classmethod
    def rows(kls, bounds):
        _, (t, b), _ = bounds
        for row in range(t, b, -1):
            yield kls.row(row, bounds)

    @classmethod
    def all_points(kls, bounds):
        for row in kls.rows(bounds):
            yield from row

    @classmethod
    def row(kls, row, bounds):
        (l, r), _, _ = bounds
        return [Point(col, row) for col in range(l, r)]

    @classmethod
    def col(kls, col, bounds):
        _, (t, b), _ = bounds
        return [Point(col, row) for row in range(t, b, -1)]

    @classmethod
    def expand(kls, bounds, amount):
        (l, r), (t, b), (w, h) = bounds
        return (l - amount, r + amount), (t + amount, b - amount), (w + amount * 2, h + amount * 2)
