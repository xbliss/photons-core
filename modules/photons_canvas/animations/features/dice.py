from photons_canvas.font import Character, dice_8, put_characters_on_canvas
from photons_canvas.animations import Animation, Finish, an_animation
from photons_canvas.animations.options import ColorOption

from photons_canvas.canvas import Canvas

from delfick_project.norms import dictobj, sb
import random
import time

full_character = Character(
    """
    ########
    ########
    ########
    ########
    ########
    ########
    ########
    ########
    """
)


class Options(dictobj.Spec):
    num_iterations = dictobj.Field(sb.integer_spec, default=1)

    roll_time = dictobj.Field(sb.float_spec, default=2)
    dice_color = dictobj.Field(ColorOption(200, 1, 1, 3500))


@an_animation("dice", Options)
class TileDiceRollAnimation(Animation):
    """A dice roll"""

    coords_straight = True

    def setup(self):
        self.remaining = self.options.num_iterations

    async def process_event(self, event):
        if not event.is_tick:
            return

        if event.state is None and self.options.num_iterations == 0:
            event.state = {"chars": -1}
            return self.make_canvas(event)

        if event.state and event.state["chars"] == -1:
            event.state = {"chars": -2}
            return self.make_canvas(event)

        if event.state and event.state["chars"] == -2:
            self.remaining -= 1
            if self.remaining <= 0 and self.options.num_iterations != -1:
                raise Finish("Reached max dice rolls")
            else:
                self.every = 0.01
                self.duration = 0
                event.state = None

        if event.state is None or time.time() - event.state["last_state"] > 0.05:
            chs = []
            while len(chs) < len(event.coords):
                chs.extend(random.sample(list(dice_8.values()), k=5))

            event.state = {
                "chars": random.sample(chs, k=len(event.coords)),
                "last_state": time.time(),
                "started": time.time() if event.state is None else event.state["started"],
            }

        if time.time() - event.state["started"] > self.options.roll_time:
            event.state = {"chars": -1}

        return self.make_canvas(event)

    def make_canvas(self, event):
        chars = event.state["chars"]
        self.retries = False

        if chars == -1:
            self.every = 0.5
            self.retries = True
            chars = [full_character] * len(event.coords)

        if chars == -2:
            self.duration = 0.5
            self.every = 0.7
            self.retries = True
            chars = [random.choice(list(dice_8.values()))] * len(event.coords)

        canvas = Canvas()
        put_characters_on_canvas(canvas, chars, event.coords, self.options.dice_color.color)
        return canvas
