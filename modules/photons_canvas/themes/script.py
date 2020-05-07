from photons_canvas.themes.appliers import types as appliers
from photons_canvas.themes.theme import Theme
from photons_canvas.coords import Coords

from photons_app import helpers as hp

from photons_control.colour import ColourParser, make_hsbks
from photons_control.script import FromGenerator
from photons_control.multizone import SetZones
from photons_messages import LightMessages
from photons_messages.fields import Color
from photons_canvas import CanvasColor

from delfick_project.norms import sb, dictobj, Meta
import logging

log = logging.getLogger("photons_canvas.themes.addon")

default_colors = [
    (0, 1, 0.3, 3500),
    (40, 1, 0.3, 3500),
    (60, 1, 0.3, 3500),
    (127, 1, 0.3, 3500),
    (239, 1, 0.3, 3500),
    (271, 1, 0.3, 3500),
    (294, 1, 0.3, 3500),
]


def with_overrides(overrides, color):
    is_tuple = isinstance(color, tuple)
    hue = color[0] if is_tuple else color.hue
    saturation = color[1] if is_tuple else color.saturation
    brightness = color[2] if is_tuple else color.brightness
    kelvin = color[3] if is_tuple else color.kelvin

    hue = overrides.get("hue", hue)
    saturation = overrides.get("saturation", saturation)
    brightness = overrides.get("brightness", brightness)
    kelvin = int(overrides.get("kelvin", kelvin))

    return hue, saturation, brightness, kelvin


class colors_spec(sb.Spec):
    def normalise(self, meta, val):
        if val is sb.NotSpecified:
            val = default_colors

        overrides = meta.everything.get("overrides", {})
        return [
            Color(**color) for i, color in enumerate(make_hsbks([[c, 1] for c in val], overrides))
        ]


class Options(dictobj.Spec):
    colors = dictobj.Field(colors_spec)
    theme = dictobj.Field(sb.string_choice_spec(appliers.keys()), default="SPLOTCH")
    duration = dictobj.Field(sb.float_spec(), default=1)
    overrides = dictobj.Field(sb.dictionary_spec)


class ApplyTheme:
    @classmethod
    def msg(kls, options, gatherer=None):
        if not isinstance(options, Options):
            options = Options.FieldSpec().normalise(Meta(options, []), options)

        theme = Theme()
        for color in options.colors:
            theme.add_hsbk(color.hue, color.saturation, color.brightness, color.kelvin)

        async def gen(reference, sender, **kwargs):
            instance = ApplyTheme(appliers[options.theme], theme)
            matrix_serials = []

            plans = sender.make_plans("capability")
            async for serial, completed, info in sender.gatherer.gather_per_serial(
                plans, reference, **kwargs
            ):
                if not completed:
                    return

                # Turn on the device
                yield LightMessages.SetLightPower(
                    level=65535, duration=options.duration, target=serial
                )

                cap = info["capability"]["cap"]

                if cap.has_matrix:
                    matrix_serials.append(serial)
                    continue

                # Apply the theme
                yield FromGenerator(
                    instance.gen(serial, cap, options.overrides, options.duration),
                    reference_override=serial,
                )

            if matrix_serials:
                log.info(hp.lc("found devices with matrix zones", serials=matrix_serials))
                yield FromGenerator(
                    instance.tile_msgs(matrix_serials, options.overrides, options.duration)
                )

        return FromGenerator(gen)

    def __init__(self, aps, theme):
        self.aps = aps
        self.theme = theme

    def gen(self, serial, cap, overrides, duration):
        if cap.has_multizone:
            if cap.has_extended_multizone:
                log.info(hp.lc("found a strip with extended multizone", serial=serial))
            else:
                log.info(hp.lc("found a strip without extended multizone", serial=serial))
            return self.zone_msgs(serial, overrides, duration)

        else:
            log.info(hp.lc("found a light with a single zone", serial=serial))
            return self.light_msgs(serial, overrides, duration)

    async def gather(self, sender, serial, kwargs, *pa, **pkw):
        plans = sender.make_plans(*pa, **pkw)
        info = await sender.gatherer.gather_all(plans, serial, **kwargs)
        if serial not in info:
            return None
        if not info[serial][0]:
            return None
        return info[serial][1]

    def zone_msgs(self, serial, overrides, duration):
        async def gen(reference, sender, **kwargs):
            colors = []

            info = await self.gather(sender, serial, kwargs, "zones")
            if info is None:
                length = 82
            else:
                length = len(info["zones"])

            for (start_index, end_index), hsbk in self.aps["1d"](length).apply_theme(self.theme):
                for _ in range(0, end_index - start_index + 1):
                    hsbk = with_overrides(overrides, hsbk)
                    colors.append([CanvasColor(*hsbk).as_dict(), 1])

            yield SetZones(colors)

        return gen

    def tile_msgs(self, serials, overrides, duration):
        async def gen(reference, sender, **kwargs):
            coords = Coords()
            for serial in serials:
                info = await self.gather(sender, serial, kwargs, "chain")
                if info is None:
                    log.warning(
                        hp.lc("Couldn't work out how many zones the device had", serial=serial)
                    )
                    continue
                coords.add_device(serial, info["chain"]["chain"])

            canvas = self.aps["2d"](coords).apply_theme(self.theme)

            for serial in serials:
                if coords.has_serial(serial):
                    device_coords = coords.for_serial(serial)
                    yield canvas.messages_for(device_coords)[0]

        return gen

    def light_msgs(self, serial, overrides, duration):
        async def gen(reference, sender, **kwargs):
            hsbk = with_overrides(overrides, self.aps["0d"]().apply_theme(self.theme))
            s = f"kelvin:{hsbk[3]} hue:{hsbk[0]} saturation:{hsbk[1]} brightness:{hsbk[2]}"
            yield ColourParser.msg(s, overrides={"duration": duration})

        return gen
