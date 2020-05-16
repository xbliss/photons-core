from photons_canvas.points.msg_maker import MsgMaker
from photons_canvas.points import containers as cont
from photons_canvas.points.color import Color


class Canvas:
    def __init__(self):
        self._parts = {}

        self.parts = []
        self.points = {}
        self.devices = []

        self.top = None
        self.left = None
        self.right = None
        self.bottom = None

        self.width = None
        self.height = None

    @classmethod
    def combine(kls, *canvases):
        new = kls()

        parts = []
        for canvas in canvases:
            for part in canvas.parts:
                parts.append((part, [canvas[point] for point in part.points]))

        new.add_parts(*parts)
        return new

    def __getitem__(self, point):
        color = self.points.get(point)
        if color is None:
            return color

        if isinstance(color, tuple):
            color = self.points[point] = self.color(*color)

        return color

    def __setitem__(self, point, color):
        contained = point in self.points
        self.points[point] = color

        if not contained:
            self.update_bounds([point])

    def __contains__(self, point):
        return point in self.points

    def __call__(self, point, canvas, parts):
        return self.points.get(point)

    def pairs(self, convert=True):
        for key in self.points:
            if convert:
                if isinstance(key, tuple):
                    key = cont.Point(*key)
                yield key, self[key]
            else:
                yield key, self.points[key]

    def clone(self):
        new = self.__class__()
        new._parts.update(self._parts)
        new.points.update(self.points)
        if self.width is not None:
            new.update_bounds([self.bounds])
        return new

    def color(self, hue, saturation, brightness, kelvin):
        return Color(hue, saturation, brightness, kelvin)

    def restore_msgs(self, *, duration=1):
        for part in self.parts:
            if part.real_part and part.real_part.original_colors:
                yield from part.msgs(
                    part.real_part.original_colors,
                    power_on=False,
                    duration=duration,
                    acks=True,
                    randomize=False,
                )

    def msgs(self, *layers, average=False, acks=False, duration=1, randomize=False):
        yield from MsgMaker(self).msgs(
            layers, average=average, acks=acks, duration=duration, randomize=randomize
        )

    @property
    def bounds(self):
        return (self.left, self.right), (self.top, self.bottom), (self.width, self.height)

    def add_parts(self, *parts):
        for part in parts:
            colors = None
            if isinstance(part, tuple):
                part, colors = part
            self._parts[part] = True
            if colors:
                for point, color in zip(part.points, colors):
                    self[point] = color

        self.parts = list(self._parts)
        self.update_bounds(self.parts)

    def update_bounds(self, parts):
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

    def parts_for_point(self, point):
        parts = []
        for part in self.parts:
            if point in part.points:
                parts.append(part)
        return parts

    def devices_for_point(self, point):
        devices = set()
        for part in self.parts:
            if point in part.points:
                devices.add(part.device)
        return list(devices)
