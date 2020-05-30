from photons_canvas import point_helpers as php

from photons_control.colour import make_hsbk

from delfick_project.norms import sb, BadSpecValue
import random


class ZeroColor:
    def __init__(self):
        self.color = None


class OneColor:
    def __init__(self, hue, saturation, brightness, kelvin):
        self.color = (hue, saturation, brightness, kelvin)


class OneColorRange:
    def __init__(self, hs, ss, bb, kk):
        self.hs = hs
        self.ss = ss
        self.bb = bb
        self.kk = kk

    @property
    def color(self):
        return (self.hue, self.saturation, self.brightness, self.kelvin)

    @property
    def hue(self):
        h = self.hs
        if h[0] != h[1]:
            h = random.randrange(h[0], h[1])
        else:
            h = h[0]
        return h % 360

    @property
    def saturation(self):
        s = self.ss
        if s[0] != s[1]:
            s = random.randrange(s[0], s[1]) / 1000
        else:
            s = s[0]

        if s < 0:
            s = 0
        elif s > 1:
            s = 1
        return s

    @property
    def brightness(self):
        b = self.bb
        if b[0] != b[1]:
            b = random.randrange(b[0], b[1]) / 1000
        else:
            b = b[0]

        if b < 0:
            b = 0
        elif b > 1:
            b = 1
        return b

    @property
    def kelvin(self):
        k = self.kk
        if k[0] != k[1]:
            k = random.randrange(k[0], k[1])
        else:
            k = k[0]

        if k < 0:
            k = 0
        elif k > 0xFFFF:
            k = 0xFFFF
        return k


class ManyColor:
    def __init__(self, colors):
        if len(colors) == 0:
            colors = [ZeroColor()]
        self.colors = colors

    @property
    def color(self):
        return random.choice(self.colors).color


class color_option_spec(sb.Spec):
    def setup(self, h, s, b, k):
        self.default = (h, s, b, k)

    def normalise_empty(self, meta):
        return self.normalise_filled(meta, self.default)

    def normalise_filled(self, meta, val):
        h, s, b, k = make_hsbk(val)
        return OneColor(*make_hsbk(val))


class color_range_spec(sb.Spec):
    def setup(self, default):
        self.default = default

    def normalise_empty(self, meta):
        return self.normalise(meta, self.default)

    def normalise_filled(self, meta, val):
        if isinstance(val, str):
            val = val.split(":")

        colors = []
        for i, r in enumerate(val):
            colors.append(self.interpret(meta.indexed_at(i), r))

        return ManyColor([c for c in colors if c is not None])

    def interpret(self, meta, val):
        if not isinstance(val, (tuple, list, str)):
            raise BadSpecValue("Each color specifier must be a list or string", got=val, meta=meta)

        if isinstance(val, str):
            val = val.split(",")

        if len(val) == 0:
            return
        elif len(val) == 1:
            val = (*val, (1, 1), (1, 1), (3500, 3500))
        elif len(val) == 2:
            val = (*val, (1, 1), (3500, 3500))
            if val[0] == "rainbow":
                val[2] = (1, 1)
        elif len(val) == 3:
            val = (*val, (3500, 3500))
        elif len(val) > 4:
            raise BadSpecValue("Each color must be 4 or less specifiers", got=val, meta=meta)

        result = []
        for i, v in enumerate(val):
            m = meta.indexed_at(i)

            if not isinstance(v, (tuple, list, str)):
                raise BadSpecValue("Each color specifier must be a list or string", got=val, meta=m)

            if i != 0 and v == "rainbow":
                raise BadSpecValue("Only hue may be given as 'rainbow'", meta=m)

            if v == "rainbow":
                result.append((0, 360))
                continue

            if isinstance(v, str):
                v = v.split("-")

            if len(v) > 2:
                raise BadSpecValue("A specifier must be two values", got=v, meta=m)

            if len(v) == 0:
                continue

            if len(v) == 1:
                v = v * 2

            if i in (1, 2):
                v = (v[0] * 1000, v[1] * 1000)

            result.append((int(v[0]), int(v[1])))

        return OneColorRange(*result)


class Rate:
    def __init__(self, mn, mx):
        self.mn = round(mn, 3)
        self.mx = round(mx, 3)

        self.constant = None
        if self.mn == self.mx:
            self.constant = self.mn

    @property
    def rate(self):
        if self.constant is not None:
            return self.connstant
        return random.randrange(self.mn * 1000, self.mx * 1000) / 1000

    def __call__(self):
        return self.rate


class rate_spec(sb.Spec):
    def setup(self, default):
        self.default = default

    def normalise_empty(self, meta):
        return self.normalise_filled(meta, self.default)

    def normalise_filled(self, meta, value):
        if isinstance(value, str):
            value = value.split("-")
        elif isinstance(value, (int, float)):
            value = (value, value)

        if not isinstance(value, (list, tuple)):
            raise BadSpecValue("Speed option must be 'min-max' or [min, max]", got=value, meta=meta)

        return Rate(value[0], value[1])
