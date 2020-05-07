from photons_canvas.animations import Animation, an_animation
from photons_canvas.animations.lines import LineOptions
from photons_canvas.canvas import Canvas, CanvasColor

from delfick_project.norms import dictobj, sb
import random


class Options(LineOptions):
    min_speed = dictobj.Field(sb.float_spec, default=0.6)
    max_speed = dictobj.Field(sb.float_spec, default=0.8)


class State:
    def __init__(self, options):
        self.lines = {}
        self.rates = {}
        self.start = {}
        self.canvas = Canvas()
        self.options = options
        self.finished = False

    def add_coords(self, event, coords, bottom_y):
        for coord in coords:
            for point in coord.points:
                if point not in event.canvas:
                    event.canvas[point] = None
                col, _ = point
                if col not in self.lines:
                    self.lines[col] = []

    def progress(self, full_canvas, bottom_y, top_y):
        if self.finished:
            return None, True

        for point, color in list(self.canvas):
            if color is None:
                continue

            fade_amount = self.options.fade_amount
            if fade_amount == 0:
                self.canvas[point] = None
            else:
                self.canvas[point].brightness -= fade_amount

        for col, lines in self.lines.items():
            self.apply_lines(col, lines, full_canvas, bottom_y, top_y)

        for point in list(self.canvas.points):
            if point not in full_canvas:
                del self.canvas[point]

        return self.canvas

    def apply_lines(self, col, lines, full_canvas, bottom_y, top_y):
        def paint_line(line):
            pixels = list(line.pixels(line.start_y))
            start_pos = pixels[0][0]

            relevant = False
            for pos, color in pixels:
                if not color:
                    continue

                if pos > top_y:
                    relevant = True

                point = (col, pos)
                if not line.blank:
                    if full_canvas.get(point, None) is not None:
                        color = CanvasColor.average([color, full_canvas[point]])
                    self.canvas[point] = color

            return start_pos, relevant

        start_pos = None
        for i, line in enumerate(lines):
            line.progress(line.rate)
            s, relevant = paint_line(line)
            if not relevant:
                lines.pop(i)

            if start_pos is None or s > start_pos:
                start_pos = s

        if start_pos is None or bottom_y - start_pos > random.randrange(7, 15):
            line = self.options.make_line(random.randrange(3, 6))
            if start_pos is None:
                line.start_y = bottom_y
            else:
                line.start_y = bottom_y + random.randrange(3, 6)
            line.rate = -self.options.make_rate()
            line.blank = random.randrange(0, 100) < 50
            line.tail = random.randrange(10, 15)
            lines.append(line)

            paint_line(line)


@an_animation("falling", Options)
class FallingAnimation(Animation):
    def setup(self):
        self.swip_canvas = Canvas()

    async def process_event(self, event):
        _, (top_y, bottom_y), _ = event.coords.bounds

        if not event.state:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.add_coords(event, event.value.coords, bottom_y)
            return

        if not event.is_tick:
            return

        canvas = event.state.progress(event.canvas, bottom_y, top_y)

        for point, color in canvas:
            if point in event.canvas:
                event.canvas[point] = color

        return event.canvas
