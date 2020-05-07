from photons_canvas.animations import Animation, an_animation
from .state import State

from photons_canvas.canvas import CanvasColor

from delfick_project.norms import dictobj, sb
import random


class Options(dictobj.Spec):
    new_color_style = dictobj.Field(sb.string_choice_spec(["random", "average"]), default="average")
    iteration_delay = dictobj.Field(sb.float_spec, default=0.1)

    def make_new_color(self, surrounding):
        if self.new_color_style == "random":
            return CanvasColor(random.randrange(0, 360), 1, 1, 3500)
        else:
            return CanvasColor.average(surrounding)


@an_animation("gameoflife", Options)
class GameOfLifeAnimation(Animation):
    """
    Run a Conway's game of life simulation on the tiles
    """

    every = 0.1
    acks = False
    duration = 0
    skip_background = True

    async def process_event(self, event):
        if not event.is_tick:
            return

        if event.state is None:
            event.state = State(self.options.make_new_color)

        event.state.set_coords(event.coords)
        event.state.iterate(self.options.iteration_delay)
        return event.state.canvas
