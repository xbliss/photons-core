from photons_canvas.points import helpers as php

from photons_app import helpers as hp

from collections import defaultdict


class MsgMaker:
    def __init__(self, canvas):
        self.canvas = canvas

    class _cache:
        def __init__(self, color, layers, average):
            self.color = color
            self.layers = layers
            self.average = average

            self.cached = {}

        def __call__(self, point):
            if point in self.cached:
                return self.cached[point]
            else:
                c = self.color(point, self.layers, average=self.average)
                self.cached[point] = c
                return c

    def _color(self, point, layers, *, average=False):
        if not layers:
            return self.canvas.points.get(point)

        parts = self.point_to_parts[point]
        colors = []

        for layer in layers:
            nxt = layer(point, self.canvas, parts)
            if nxt is not None:
                if not average:
                    return nxt
                else:
                    colors.append(nxt)

        return php.average_color(colors)

    @hp.memoized_property
    def point_to_parts(self):
        point_to_parts = defaultdict(list)
        for part in self.canvas.parts:
            for point in part.points:
                point_to_parts[point].append(part)
        return point_to_parts

    def msgs(self, layers, average=False, acks=False, duration=1, randomize=False):
        cache = self._cache(self._color, layers, average=average)

        for part in self.canvas.parts:
            yield from part.msgs(
                [cache(point) for point in part.points],
                acks=acks,
                duration=duration,
                randomize=randomize,
            )
