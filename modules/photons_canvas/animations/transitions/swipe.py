from photons_canvas.animations import Animation, Finish, an_animation
from photons_canvas.animations.lines import LineOptions
from photons_canvas.canvas import Canvas

from delfick_project.norms import dictobj, sb
import random


class Options(LineOptions):
    min_speed = dictobj.Field(sb.float_spec, default=1.5)
    max_speed = dictobj.Field(sb.float_spec, default=2)


class State:
    def __init__(self, options):
        self.lines = {}
        self.rates = {}
        self.start = {}
        self.canvas = Canvas()
        self.options = options
        self.finished = False

    def add_coords(self, coords, right_x):
        for coord in coords:
            for (_, row) in coord.points:
                if row not in self.lines:
                    self.start[row] = right_x
                    self.rates[row] = -self.options.make_rate()
                    self.lines[row] = self.options.make_line(random.randrange(1, 5))

    def progress(self):
        for row, line in self.lines.items():
            line.progress(self.rates[row])

    def make_canvas(self, full_canvas):
        if self.finished:
            return None, True

        for point, color in list(self.canvas):
            fade_amount = self.options.fade_amount

            color = color.clone()
            if fade_amount == 0:
                color.brightness = 0
            else:
                color.brightness -= fade_amount

            if color.brightness <= 0:
                c = full_canvas[point].clone()
                c.brightness = 0
                full_canvas[point] = c
                del self.canvas[point]
            else:
                self.canvas[point] = color

        for row, line in self.lines.items():
            for i, pixel in line.pixels(self.start[row], reverse=True):
                self.canvas[(i, row)] = pixel

        for point in list(self.canvas.points):
            if point not in full_canvas:
                del self.canvas[point]
                finished = False

        finished = self.finished
        if not self.canvas:
            self.finished = True

        return self.canvas, finished


@an_animation("swipe", Options, transition=True)
class Animation(Animation):
    def setup(self):
        self.swip_canvas = Canvas()

    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options)

        if event.is_new_device:
            (left_x, _), _, (width, _) = event.coords.bounds
            event.state.add_coords(event.value.coords, left_x + width)
            return

        if not event.is_tick:
            return

        event.state.progress()

        canvas, finished = event.state.make_canvas(event.canvas)

        if finished:
            raise Finish("Tiles are swiped")

        for point, color in canvas:
            if point in event.canvas:
                event.canvas[point] = color

        return event.canvas
