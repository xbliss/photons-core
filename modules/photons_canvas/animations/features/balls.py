from photons_canvas.animations.options import (
    split_by_comma,
    hue_range_spec,
    HueRange,
    normalise_speed_options,
)
from photons_canvas.animations import Animation, an_animation
from photons_canvas.canvas import CanvasColor

from delfick_project.norms import dictobj, sb
from collections import defaultdict
import random
import math


class Options(dictobj.Spec):
    ball_hues = dictobj.NullableField(split_by_comma(hue_range_spec()), default=[])
    num_balls = dictobj.Field(sb.integer_spec, default=5)
    fade_amount = dictobj.Field(sb.float_spec, default=0.02)

    min_speed = dictobj.Field(sb.float_spec, default=0.6)
    max_speed = dictobj.Field(sb.float_spec, default=0.8)


class Boundary:
    def __init__(self):
        self.points = {}
        self.position_points = []

    def set_coords(self, coords):
        for point in coords.all_points:
            self.points[point] = True

        self.position_points = list(self.points)

    def random_coord(self):
        if not self.position_points:
            return (0, 0)
        return random.choice(self.position_points)

    def is_going_outside(self, now, nxt, dx, dy):
        combined = now + nxt
        most_left = min(x for x, _ in combined)
        most_right = max(x for x, _ in combined)
        most_top = max(y for _, y in combined)
        most_bottom = min(y for _, y in combined)

        if dx < 0:
            now_x = min(x for x, _ in now)
        else:
            now_x = max(x for x, _ in now)

        if dy < 0:
            now_y = min(y for _, y in now)
        else:
            now_y = max(y for _, y in now)

        outside_x = 0
        outside_y = 0

        for i in range(most_left, most_right + 1):
            for j in range(most_bottom, most_top + 1):
                point = (i, j)
                if point not in self.points and point not in now:
                    if dx < 0:
                        if point[0] < now_x:
                            outside_x += 1
                    else:
                        if point[0] > now_x:
                            outside_x += 1

                    if dy < 0:
                        if point[1] < now_y:
                            outside_y += 1
                    else:
                        if point[1] > now_y:
                            outside_y += 1

        return outside_x >= 2, outside_y >= 2


class Ball:
    def __init__(self, boundary, hue, rate_x, rate_y):
        self.hue = hue
        self.boundary = boundary

        self.x, self.y = self.boundary.random_coord()
        self.dx = rate_x
        self.dy = rate_y
        self.extrax = 0
        self.extray = 0
        self.maybe_alter_course()

    def maybe_alter_course(self):
        points_now = [(math.floor(x), math.floor(y)) for x, y in self.points]
        points_next = [(math.floor(x), math.floor(y)) for x, y in self.next_points]
        outside_x, outside_y = self.boundary.is_going_outside(
            points_now, points_next, self.dx, self.dy
        )

        if not outside_x and not outside_y:
            return

        if outside_x:
            self.dx *= -1

        if outside_y:
            self.dy *= -1

        self.extra_x = random.randrange(0, 5) / 10
        self.extra_y = random.randrange(0, 5) / 10

        if (self.dy < 0) ^ (self.extra_y < 0):
            self.extra_y *= -1

        if (self.dx < 0) ^ (self.extra_x < 0):
            self.extra_x *= -1

    @property
    def top(self):
        return self.y

    @property
    def bottom(self):
        return self.y - 1

    @property
    def right(self):
        return self.x + 1

    @property
    def left(self):
        return self.x

    @property
    def points(self):
        return [
            (self.x, self.y),
            (self.x, self.y - 1),
            (self.x + 1, self.y),
            (self.x + 1, self.y - 1),
        ]

    @property
    def next_points(self):
        x, y = self.next_point()
        return [(x, y), (x, y - 1), (x + 1, y), (x + 1, y - 1)]

    def next_point(self):
        x = self.x + self.dx + self.extrax
        y = self.y + self.dy + self.extray
        return x, y

    def progress(self):
        self.x, self.y = self.next_point()
        self.maybe_alter_course()

    def pixels(self):
        for x, y in self.points:
            yield (math.floor(x), math.floor(y)), CanvasColor(self.hue, 1, 1, 3500)


class TileBallsState:
    def __init__(self, canvas, options):
        self.options = options
        self.balls = []
        self.boundary = Boundary()
        self.ensure_enough_balls()
        self.canvas = canvas

    def set_coords(self, coords):
        self.boundary.set_coords(coords)

    def ensure_enough_balls(self):
        need = self.options.num_balls - len(self.balls)
        if need > 0:
            self.balls.extend([self.make_ball() for _ in range(need)])

    def make_ball(self):
        if self.options.min_speed == self.options.max_speed:
            rate_x = self.options.min_speed
            rate_y = self.options.max_speed
        else:
            mn = int(self.options.min_speed * 100)
            mx = int(self.options.max_speed * 100)
            rate_x = random.randint(mn, mx) / 100
            rate_y = random.randint(mn, mx) / 100

        if random.randrange(0, 100) < 50:
            rate_x *= -1
        if random.randrange(0, 100) < 50:
            rate_y *= -1

        ball_hue = random.choice(self.options.ball_hues)
        return Ball(self.boundary, ball_hue.make_hue(), rate_x, rate_y)

    def tick(self):
        for ball in self.balls:
            ball.progress()
        return self

    def make_canvas(self):
        for point, pixel in list(self.canvas):
            pixel.brightness -= self.options.fade_amount
            if pixel.brightness < 0:
                del self.canvas[point]

        pixels = defaultdict(list)
        for ball in self.balls:
            for point, pixel in ball.pixels():
                pixels[point].append(ball)
                self.canvas[point] = pixel

        collided_balls = []
        for balls in pixels.values():
            if len(balls) > 1:
                collided_balls.extend(balls)
                for ball in balls:
                    for point, _ in ball.pixels():
                        self.canvas[point] = CanvasColor(0, 0, 1, 3500)

        self.balls = [b for b in self.balls if b not in collided_balls]
        self.ensure_enough_balls()
        return self.canvas


@an_animation("balls", Options)
class TileBallsAnimation(Animation):
    """Bouncing balls"""

    def setup(self):
        normalise_speed_options(self.options)
        if not self.options.ball_hues:
            self.options.ball_hues = [HueRange(0, 360)]

    async def process_event(self, event):
        if event.state is None:
            event.state = TileBallsState(event.canvas, self.options)

        if event.is_new_device:
            event.state.set_coords(event.coords)
            return

        event.state.tick()
        return event.state.make_canvas()
