from photons_canvas.animations import Animation, Finish, an_animation
from photons_canvas.canvas import CanvasColor

from delfick_project.norms import dictobj
import random


class Options(dictobj.Spec):
    pass


class State:
    def __init__(self, coords):
        self.color = CanvasColor(random.randrange(0, 360), 1, 1, 3500)

        self.wait = 0
        self.remaining = {}
        self.all_points = {}

    def add_coords(self, coords):
        for coord in coords:
            for point in coord.points:
                self.remaining[point] = True
                self.all_points[point] = True

    def progress(self):
        if not self.all_points:
            return

        amount = len(self.all_points) // 15
        next_selection = random.sample(list(self.remaining), k=min(len(self.remaining), amount))

        for point in next_selection:
            del self.remaining[point]


@an_animation("dots", Options, transition=True)
class Animation(Animation):
    coords_separate = True

    async def process_event(self, event):
        if event.state is None:
            event.state = State(event.coords)

        if event.is_new_device:
            event.state.add_coords(event.value.coords)
            return

        if not event.is_tick:
            return

        event.state.progress()

        if not event.state.remaining:
            self.acks = True
            event.state.wait += 1

        if event.state.wait == 2:
            self.every = 1
            self.duration = 1

        if event.state.wait == 3:
            raise Finish("Transition complete")

        color = event.state.color
        if event.state.wait > 1:
            color = CanvasColor(0, 0, 0, 3500)

        for point in event.canvas.points:
            if point not in event.state.remaining:
                event.canvas[point] = color

        return event.canvas
