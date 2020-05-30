from photons_canvas.points import helpers as php

from delfick_project.norms import sb
from collections import defaultdict


class Canvas:
    def __init__(self):
        self._parts = {}

        self.points = {}
        self.devices = []

        self.top = None
        self.left = None
        self.right = None
        self.bottom = None

        self.width = None
        self.height = None

        self.point_to_parts = defaultdict(set)
        self.point_to_devices = defaultdict(set)

    def __getitem__(self, point):
        return self.points.get(point)

    def __setitem__(self, point, color):
        contained = point in self.points
        self.points[point] = color

        if not contained:
            self._update_bounds([point])

    def __delitem__(self, point):
        if point not in self.points:
            return

        del self.points[point]
        self._update_bounds(self.points)

    def __bool__(self):
        return bool(self._parts) or bool(self.points)

    def __call__(self, point, canvas, parts):
        return self.points.get(point)

    @property
    def parts(self):
        return list(self._parts)

    @property
    def bounds(self):
        return (self.left, self.right), (self.top, self.bottom), (self.width, self.height)

    def clone(self):
        new = self.__class__()
        new._parts.update(self._parts)
        new.points.update(self.points)
        new.point_to_parts.update(self.point_to_parts)
        new.point_to_devices.update(self.point_to_devices)

        if self.width is not None:
            new._update_bounds([self.bounds])

        return new

    def is_parts(self, hue=None, brightness=None, saturation=None, kelvin=None):
        for part in self.parts:
            for point in php.Points.all_points(part.bounds):
                color = self[point]
                if color is None:
                    continue

                h, s, b, k = color

                if hue is not None and h != hue:
                    return False
                if saturation is not None and s != saturation:
                    return False
                if brightness is not None and b != brightness:
                    return False
                if kelvin is not None and k != kelvin:
                    return False

        return True

    def override(
        self, point, hue=None, saturation=None, brightness=None, kelvin=None,
    ):
        return php.Color.override(
            self[point] or (0, 0, 0, 0),
            hue=hue,
            saturation=saturation,
            brightness=brightness,
            kelvin=kelvin,
        )

    def dim(self, point, change):
        current = self.points.get(point)
        if not current or current[2] == 0:
            return None

        b = current[2] - change
        if b <= 0:
            return None

        return current[0], current[1], b, current[3]

    def adjust(
        self,
        point,
        hue_change=None,
        saturation_change=None,
        brightness_change=None,
        kelvin_change=None,
        ignore_empty=True,
    ):
        current = self.points.get(point)
        if ignore_empty and current in php.Color.EMPTIES:
            return None

        return php.Color.adjust(
            current or php.Color.ZERO,
            hue_change=hue_change,
            saturation_change=saturation_change,
            brightness_change=brightness_change,
            kelvin_change=kelvin_change,
        )

    def restore_msgs(self, *, duration=1):
        for part in self.parts:
            if part.real_part and part.real_part.original_colors:
                yield from part.real_part.msgs(
                    part.real_part.original_colors,
                    power_on=False,
                    duration=duration,
                    acks=True,
                    randomize=False,
                )

    def msgs(self, layer, acks=False, duration=1, randomize=False, onto=None):
        msgs = []
        cache = {}

        for part in self.parts:
            cs = []
            for point in part.points:
                c = cache.get(point)

                if c is None:
                    c = layer(point, self)

                    if onto:
                        onto[point] = c

                    cache[point] = c

                cs.append(c)

            for msg in part.msgs(cs, acks=acks, duration=duration, randomize=randomize):
                msgs.append(msg)

        return msgs

    def add_parts(self, *parts, with_colors=False, zero_color=sb.NotSpecified):
        for part in parts:
            colors = None

            if isinstance(part, tuple):
                part, colors = part

            if not colors and with_colors and part.colors:
                colors = part.colors

            if colors is None and zero_color is not sb.NotSpecified:
                colors = [zero_color] * php.Points.count_points(part.bounds)

            self._parts[part] = True
            if colors:
                for point, color in zip(part.points, colors):
                    self[point] = color

            for point in php.Points.all_points(part.bounds):
                self.point_to_parts[point].add(part)
                self.point_to_parts[point].add(part.device)

        self._update_bounds(self.parts)

    def _update_bounds(self, parts):
        if not parts:
            return

        top = self.top
        left = self.left
        right = self.right
        bottom = self.bottom

        for part in parts:
            if isinstance(part, tuple):
                if len(part) == 2:
                    bounds = ((part[0], part[0]), (part[1], part[1]), (0, 0))
                else:
                    bounds = part
            else:
                bounds = part.bounds

            (l, r), (t, b), _ = bounds

            top = top if top is not None and t < top else t
            left = left if left is not None and l > left else l
            right = right if right is not None and r < right else r
            bottom = bottom if bottom is not None and b > bottom else b

        self.top = top
        self.left = left
        self.right = right
        self.bottom = bottom

        self.width = self.right - self.left
        self.height = self.top - self.bottom
