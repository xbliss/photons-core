from photons_canvas.animations import options, Animation, an_animation
from photons_canvas.font import put_characters_on_canvas, alphabet_8
from photons_canvas import Canvas, GetColor

from delfick_project.norms import dictobj, sb
import time


class Options(dictobj.Spec):
    hour24 = dictobj.Field(sb.boolean, default=True)
    number_color = dictobj.Field(options.ColorOption(50, 1, 0.6, 3500))
    progress_bar_color = dictobj.Field(options.ColorOption(200, 0.5, 0.2, 3500))
    full_height_progress = dictobj.Field(sb.boolean, default=False)


@an_animation("time", Options)
class TileTimeAnimation(Animation):
    """Print time to the tiles"""

    every = 1.5
    duration = 1
    retries = True
    coords_straight = True

    class State:
        def __init__(self, time_string, second):
            self.time_string = time_string
            self.second = second

    async def process_event(self, event):
        if not event.is_tick:
            return

        localtime = time.localtime(time.time())
        second = localtime.tm_sec
        minute = localtime.tm_min
        hour = localtime.tm_hour
        if not self.options.hour24 and (hour > 12):
            hour = hour - 12
        if not self.options.hour24 and hour == 0:
            hour = 12

        event.state = self.State("{:02d}:{:02d}".format(hour, minute), second)

        canvas = Canvas()
        (left_x, _), _, (width, _) = event.coords.bounds
        seconds_line_length = width * (event.state.second / 60)

        class GC(GetColor):
            def __call__(s, x, y):
                position = s.coord.left_x - left_x + x
                if self.options.full_height_progress or y == s.coord.height - 1:
                    if position < seconds_line_length:
                        return self.options.progress_bar_color.color

        # Add the seconds progress
        canvas.set_all_points_for_coords(event.coords, GC)

        # Add the numbers
        time_characters = [alphabet_8[ch] for ch in list(event.state.time_string)]
        put_characters_on_canvas(
            canvas, time_characters, event.coords, self.options.number_color.color
        )

        return canvas
