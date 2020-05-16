from delfick_project.norms import sb
import enum


class HSBKE(enum.Enum):
    HUE = "hue"
    SATURATION = "saturation"
    BRIGHTNESS = "brightness"
    KELVIN = "kelvin"


HSBKEV = (HSBKE.HUE.value, HSBKE.SATURATION.value, HSBKE.BRIGHTNESS.value, HSBKE.KELVIN.value)


class Color:
    __slots__ = ["is_dict", "_as_dict", "_hash", "_tuple", *HSBKEV]

    def __init__(self, hue, saturation, brightness, kelvin):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin

        self.is_dict = True
        self._tuple = (self.hue, self.saturation, self.brightness, self.kelvin)
        self._hash = hash(self._tuple)

    def __repr__(self):
        return f"<Color ({self.hue},{self.saturation},{self.brightness},{self.kelvin})>"

    def __hash__(self):
        return self._hash

    def __iter__(self):
        yield from self._tuple

    def __lt__(self, other):
        if isinstance(other, tuple):
            return self._tuple < other
        else:
            return self._tuple < other._tuple

    def __eq__(self, other):
        if isinstance(other, tuple) and other == self._tuple:
            return True

        if not all(hasattr(other, k) for k in HSBKEV):
            return False

        return (
            other.hue == self.hue
            and other.saturation == self.saturation
            and other.brightness == self.brightness
            and other.kelvin == self.kelvin
        )

    def clone(
        self,
        hue=sb.NotSpecified,
        saturation=sb.NotSpecified,
        brightness=sb.NotSpecified,
        kelvin=sb.NotSpecified,
    ):
        h = self.hue if hue is sb.NotSpecified else hue
        s = self.saturation if saturation is sb.NotSpecified else saturation
        b = self.brightness if brightness is sb.NotSpecified else brightness
        k = self.kelvin if kelvin is sb.NotSpecified else kelvin
        return self.__class__(h, s, b, k)

    def as_dict(self):
        if not hasattr(self, "_as_dict"):
            self._as_dict = {
                HSBKE.HUE.value: self.hue,
                HSBKE.SATURATION.value: self.saturation,
                HSBKE.BRIGHTNESS.value: self.brightness,
                HSBKE.KELVIN.value: self.kelvin,
            }
        return self._as_dict

    def get(self, key, default=None):
        if key == HSBKE.HUE.value:
            return self.hue
        if key == HSBKE.SATURATION.value:
            return self.saturation
        if key == HSBKE.BRIGHTNESS.value:
            return self.brightness
        if key == HSBKE.KELVIN.value:
            return self.kelvin

        return default
