from photons_tile_paint.options import AnimationOptions, ColorOption
from photons_tile_paint.marquee.animation import MarqueeDirection
from photons_protocol.types import enum_spec

from delfick_project.norms import dictobj, sb


class TileMarqueeOptions(AnimationOptions):
    text_color = dictobj.Field(ColorOption(200, 0.24, 0.5, 3500))
    text = dictobj.Field(sb.string_spec, default="LIFX is awesome!")
    user_coords = dictobj.Field(sb.boolean, default=False)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    large_font = dictobj.Field(sb.boolean, default=False)
    speed = dictobj.Field(sb.integer_spec, default=1)
    direction = dictobj.Field(
        enum_spec(MarqueeDirection, unpacking=True), default=MarqueeDirection.LEFT
    )

    @property
    def text_width(self):
        if self.large_font:
            return len(self.text) * 16
        else:
            return len(self.text) * 8

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration
