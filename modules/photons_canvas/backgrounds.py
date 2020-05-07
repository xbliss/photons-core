from photons_canvas.canvas import Canvas, CanvasColor
from photons_control.colour import ColourParser

from delfick_project.norms import sb, BadSpecValue


class background_spec(sb.Spec):
    def setup(self, for_transition=False):
        self.for_transition = for_transition

    def normalise_empty(self, meta):
        if self.for_transition:
            return Background(clear=False, as_start=True)
        else:
            return Background()

    def normalise_filled(self, meta, val):
        if isinstance(val, Background):
            return val

        val = sb.string_spec().normalise(meta, val)
        if val == "clear":
            return Background()

        elif val.startswith("maintain"):
            color = None
            if ":" in val:
                color = val.split(":", 1)[1]
            return Background(clear=False, maintain=True, color=color)

        elif val.startswith("as_start"):
            color = None
            if ":" in val:
                color = val.split(":", 1)[1]
            return Background(clear=False, as_start=True, color=color)

        else:
            raise BadSpecValue(
                "Background option must be clear, maintain, as_start, maintain:<color> or as_start:<color>",
                got=val,
            )


class Background:
    def __init__(self, clear=True, maintain=False, as_start=False, color=""):
        self.clear = clear
        self.color = color
        self.maintain = maintain
        self.as_start = as_start

        self.empty_color = CanvasColor(0, 0, 0, 3500)

        if self.color:
            msg = ColourParser.msg(self.color)
            if msg.brightness == 0:
                msg.brightness = 0.3
            self.empty_color = CanvasColor(msg.hue, msg.saturation, msg.brightness, msg.kelvin)

    def colors(self, canvas, background_canvas, coord):
        nc = Canvas()

        def get_color(x, y):
            for c in (canvas, background_canvas):
                if c:
                    result = c.get((x, y), None)
                    if result is not None:
                        return result
            return self.empty_color

        nc.set_default_color_func(get_color)
        return nc.points_for_coord(coord)

    def background_canvas(self, colors, coords):
        if self.maintain:
            canvas = Canvas()
            self.add_to_canvas(canvas, colors, coords)
            return canvas

    def start_canvas(self, colors, coords):
        canvas = Canvas()
        self.add_to_canvas(canvas, colors, coords)
        return canvas

    def add_start(self, canvas, colors, coords):
        if self.as_start:
            self.add_to_canvas(canvas, colors, coords)

    def add_to_canvas(self, canvas, colors, coords):
        if self.clear or self.color:
            for coord in coords:
                self._set_color(canvas, coord, self.empty_color)
        else:
            for coord, colors in zip(coords, colors):
                if coord and colors:
                    self._set_from_colors(canvas, coord, colors)

    def _set_color(self, canvas, coord, color):
        canvas.set_all_points_for_coord(coord, lambda *args: color)

    def _set_from_colors(self, canvas, coord, colors):
        for point, color in zip(coord.points, colors):
            if point and color:
                canvas[point] = CanvasColor(
                    color.hue, color.saturation, color.brightness, color.kelvin
                )
