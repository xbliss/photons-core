from photons_canvas.font import character_color_func
from photons_canvas import Coord
from .font import characters

from photons_canvas.canvas import CanvasColor, Canvas

import random
import time


class State:
    def __init__(self, make_new_color):
        self.coords = None
        self.canvas = Canvas()
        self.last_random = time.time()
        self.last_iteration = None
        self.make_new_color = make_new_color

    def set_coords(self, coords):
        (self.left, self.right), (self.top, self.bottom), (self.width, self.height) = coords.bounds

        if not self.coords:
            self.coords = coords
            self.place_random(4)

    def place_random(self, amount):
        for _ in range(amount):
            ch = random.choice(characters)
            left, top = self.random_coord()
            color = CanvasColor(random.randrange(0, 360), 1, 1, 3500)
            self.canvas.set_all_points_for_coord(
                Coord.simple(left, top, ch.width, ch.height), character_color_func([ch], color)
            )

    def iterate(self, delay):
        if self.last_iteration is not None and time.time() - self.last_iteration < delay:
            return self

        now = time.time()
        self.last_iteration = now

        if now - self.last_random > 1:
            self.place_random(random.randrange(0, 3))
            self.last_random = now

        removal = []
        addition = []

        points = [point for point, _ in self.canvas]

        dead_points = []
        for point in points:
            dead_points.extend([p for p in self.canvas.surrounding_points(point, all_points=True)])

        points.extend(dead_points)

        for point in set(points):
            alive = point in self.canvas
            alive_neighbours = len(self.canvas.surrounding_points(point))

            if alive:
                if alive_neighbours < 2 or alive_neighbours > 3:
                    removal.append(point)
            else:
                if alive_neighbours == 3:
                    addition.append(point)

        for point in removal:
            del self.canvas[point]

        for point in addition:
            color = self.make_new_color(
                [self.canvas[point] for point in self.canvas.surrounding_points(point)]
            )
            self.canvas[point] = color

        for (left, top), _ in list(self.canvas):
            too_far_left = left < self.left - 20
            too_far_right = left > self.right + 20
            too_far_up = top > self.top + 20
            too_far_down = top < self.bottom - 20
            if too_far_left or too_far_right or too_far_up or too_far_down:
                del self.canvas[(left, top)]

        return self

    def random_coord(self):
        left = random.randrange(self.left, self.right)
        top = random.randrange(self.bottom, self.top)
        return left, top
