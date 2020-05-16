from photons_canvas.orientation import Orientation, reorient, reverse_orientation
from photons_canvas.points.simple_messages import Set64, MultizoneMessagesMaker
from photons_canvas.points import helpers as php

from photons_app import helpers as hp

from photons_messages import LightMessages

import random


class Point:
    __slots__ = ["col", "row", "key", "_hash"]

    def __init__(self, col, row):
        self.col = col
        self.row = row
        self.key = (col, row)
        self._hash = hash(self.key)

    def __repr__(self):
        return f"<Point ({self.col},{self.row})>"

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, tuple) and other == self.key:
            return True

        if not any(hasattr(other, k) for k in ("row", "col")):
            return False

        return other.row == self.row and other.col == self.col

    def __lt__(self, other):
        if isinstance(other, tuple):
            return self.key < other
        else:
            return self.key < other.key

    def __iter__(self):
        yield from self.key

    @property
    def bounds(self):
        return (self.col, self.col), (self.row, self.row), (0, 0)

    def relative(self, bounds):
        (l, _), (t, _), _ = bounds
        col = self.col - l
        row = t - self.row
        return Point(col, row)


class Part:
    __slots__ = [
        "left",
        "right",
        "top",
        "bottom",
        "user_x",
        "user_y",
        "width",
        "height",
        "real_part",
        "part_number",
        "orientation",
        "random_orientation",
        "original_colors",
        "device",
        "_key",
        "_hash",
        "_points",
    ]

    def __init__(
        self,
        user_x,
        user_y,
        width,
        height,
        part_number,
        orientation,
        device,
        real_part=None,
        original_colors=None,
    ):
        self.device = device
        self.real_part = self if real_part is None else real_part
        self.original_colors = original_colors
        self.orientation = orientation
        self.part_number = part_number
        self.update(user_x, user_y, width, height)
        self.random_orientation = random.choice(list(Orientation.__members__.values()))

        self._key = (self.device, self.part_number)
        self._hash = hash(self._key)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, tuple) and other == self._key:
            return True

        if not any(hasattr(other, k) for k in ("device", "part_number")):
            return False

        return self.device == other.device and self.part_number == other.part_number

    def __lt__(self, other):
        if isinstance(other, tuple):
            return self._key < other
        else:
            return self._key < other._key

    def __repr__(self):
        return f"<Part ({self.device.serial},{self.part_number})>"

    def clone(self, *, user_x=None, user_y=None, width=None, height=None):
        ux = self.user_x if user_x is None else user_x
        uy = self.user_y if user_y is None else user_y
        w = self.width if width is None else width
        h = self.height if height is None else height

        return Part(
            ux,
            uy,
            w,
            h,
            self.part_number,
            self.orientation,
            self.device,
            real_part=self.real_part,
            original_colors=self.original_colors,
        )

    def update(self, user_x, user_y, width, height):
        self.width = width
        self.height = height
        self.user_x = user_x
        self.user_y = user_y

        user_x_real = int(self.user_x * 8)
        user_y_real = int(self.user_y * 8)

        self.left = user_x_real
        self.right = user_x_real + self.width

        self.top = user_y_real
        self.bottom = user_y_real - self.height

        del self.points

    @property
    def bounds(self):
        return (self.left, self.right), (self.top, self.bottom), (self.width, self.height)

    @hp.memoized_property
    def points(self):
        points = []
        for row in php.Points.rows(self.bounds):
            points.extend(row)
        return points

    def reverse_orient(self, colors):
        o = reverse_orientation(self.orientation)
        return reorient(colors, o)

    def reorient(self, colors, *, randomize=False):
        o = self.orientation
        if randomize:
            o = self.random_orientation

        return reorient(colors, o)

    def msgs(self, colors, *, power_on=False, acks=False, duration=1, randomize=False):
        if power_on:
            yield LightMessages.SetLightPower(
                target=self.device.serial, level=65535, duration=duration
            )

        if self.device.cap.has_matrix:
            colors = [
                c if c is not None else None for c in self.reorient(colors, randomize=randomize)
            ]

            yield Set64(
                x=0,
                y=0,
                length=1,
                tile_index=self.part_number,
                colors=colors,
                ack_required=acks,
                width=self.width,
                duration=duration,
                res_required=False,
                target=self.device.serial,
            )

        elif self.device.cap.has_multizone:
            yield from MultizoneMessagesMaker(
                self.device.serial, self.device.cap, colors, duration=duration
            ).msgs

        elif colors:
            if isinstance(colors[0], tuple):
                h, s, b, k = colors[0]
                info = {
                    "hue": h,
                    "saturation": s,
                    "brightness": b,
                    "kelvin": k,
                }
            else:
                info = colors[0].as_dict()

            info["duration"] = duration
            yield LightMessages.SetColor(target=self.device.serial, res_required=False, **info)


class Device:
    __slots__ = ["serial", "cap", "_hash"]

    def __init__(self, serial, cap):
        self.cap = cap
        self.serial = serial
        self._hash = hash(self.serial)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, str) and other == self.serial:
            return True

        if not hasattr(other, "serial"):
            return False

        return other.serial == self.serial

    def __lt__(self, other):
        if isinstance(other, str):
            return self.serial < other
        else:
            return self.serial < other.serial

    def __repr__(self):
        name = self.cap
        if hasattr(self.cap, "product"):
            name = self.cap.product.name
        return f"<Device ({self.serial},{name})>"
