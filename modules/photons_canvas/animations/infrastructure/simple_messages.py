"""
A simplified implementation of messages.

The normal implementation of messages in photons is very flexible and has many
features. Unfortunately this means that when we want to generate 5 Set64
messages every 0.075 seconds we can't make them fast enough.

This file contains a more manual implementation of the Set64 message that tries
to be as efficient as possible to allow us to keep up with the animation.
"""
from photons_protocol.packing import PacketPacking
from photons_messages.fields import Color
from photons_messages import TileMessages

from lru import LRU
import binascii
import bitarray
import struct

ColorCache = LRU(8000)
TargetCache = LRU(1000)

seed_set64_bytes = (
    TileMessages.Set64.empty_normalise(
        source=0,
        sequence=0,
        target="d073d5000000",
        res_required=False,
        ack_required=False,
        tile_index=0,
        length=1,
        x=0,
        y=0,
        width=8,
        duration=0,
        colors=[],
    )
    .pack()
    .tobytes()
)


class Payload:
    def __init__(self, bts):
        self._bts = bts

    def __setitem__(self, rng, value):
        if isinstance(rng, int):
            self._bts[rng + 36] = value
        else:
            self._bts[rng.start + 36 : rng.stop + 36] = value

    def __getitem__(self, rng):
        if isinstance(rng, int):
            return self._bts[rng + 36]
        return self._bts[rng.start + 36 : rng.stop + 36]


class Set64:
    def __init__(self, *, bts=None, **kwargs):
        if bts:
            self._bts = bts
        else:
            self._bts = bytearray(seed_set64_bytes)

        self.payload = Payload(self._bts)
        self.update(kwargs)

    def update(self, values):
        for k, v in values.items():
            setattr(self, k, v)

    def actual(self, key):
        if key == "duration":
            return self.duration * 1000
        return getattr(self, key)

    def simplify(self):
        return self

    def clone(self):
        return Set64(bts=bytearray(self._bts))

    def tobytes(self, serial=None):
        return bytes(self._bts)

    @property
    def is_dynamic(self):
        return False

    def pack(self):
        b = bitarray.bitarray(endian="little")
        b.frombytes(self._bts)
        return b

    def __getitem__(self, rng):
        return self._bts[rng]

    def __setitem__(self, rng, value):
        self._bts[rng] = value

    @property
    def size(self):
        """returns the size of the total message."""
        return struct.unpack("<H", self[0:2])[0]

    @size.setter
    def size(self, value):
        self[0:2] = struct.pack("<H", value)

    @property
    def protocol(self):
        """returns the protocol version of the header."""
        v = struct.unpack("<H", self[2:4])[0]
        return v & 0b111111111111

    @protocol.setter
    def protocol(self, value):
        current = struct.unpack("<H", self[2:4])[0]
        mask = 0b111111111111
        invmask = 0b1111000000000000
        self[2:4] = current & invmask | value & mask

    @property
    def addressable(self):
        """returns whether the addressable bit is set."""
        v = self[3]
        v = v >> 4
        return (v & 0b1) != 0

    @addressable.setter
    def addressable(self, value):
        v = int(bool(value))
        current = self[3]

        mask = 0b10000
        invmask = 0b1111111111101111

        self[3] = current & invmask | v << 4 & mask

    @property
    def tagged(self):
        """returns whether the tagged bit is set."""
        v = self[3]
        v = v >> 5
        return (v & 0b1) != 0

    @tagged.setter
    def tagged(self, value):
        v = int(bool(value))
        current = self[3]

        mask = 0b10000
        invmask = 0b1111111111101111

        self[3] = current & invmask | v << 5 & mask

    @property
    def source(self):
        """returns then number used by clients to differentiate themselves from other clients"""
        return struct.unpack("<I", self[4:8])[0]

    @source.setter
    def source(self, value):
        self[4:8] = struct.pack("<I", value)

    @property
    def target(self):
        """returns the target Serial from the header."""
        bts = bytes(self[8:16])
        s = TargetCache.get(bts)

        if not s:
            s = binascii.hexlify(bts[:6]).decode()
            TargetCache[bts] = s

        return s

    @target.setter
    def target(self, serial):
        bts = TargetCache.get(serial)
        if not bts:
            bts = binascii.unhexlify(serial)[:6] + b"\x00\x00"
            TargetCache[serial] = bts
        self[8:16] = bts

    @property
    def response_required(self):
        """returns whether the response required bit is set in the header."""
        v = self[22]
        return (v & 0b1) != 0

    @response_required.setter
    def response_required(self, value):
        v = int(bool(value))
        current = self[22]

        mask = 0b10000
        invmask = 0b1111111111101111

        self[22] = current & invmask | v & mask

    @property
    def ack_required(self):
        """returns whether the ack required bit is set in the header."""
        v = self[22]
        v = v >> 1
        return (v & 0b1) != 0

    @ack_required.setter
    def ack_required(self, value):
        v = int(bool(value))
        current = self[22]

        mask = 0b10000
        invmask = 0b1111111111101111

        self[22] = current & invmask | v << 1 & mask

    @property
    def sequence(self):
        """returns the sequence ID from the header."""
        return self[23]

    @sequence.setter
    def sequence(self, value):
        self[23] = value

    @property
    def pkt_type(self):
        """returns the Payload ID for the accompanying payload in the message."""
        return struct.unpack("<H", self[32:34])[0]

    @pkt_type.setter
    def pkt_type(self, value):
        self[32:34] = struct.pack("<H", value)

    @property
    def tile_index(self):
        return self.payload[0]

    @tile_index.setter
    def tile_index(self, value):
        self.payload[0] = value

    @property
    def length(self):
        return self.payload[1]

    @length.setter
    def length(self, value):
        self.payload[1] = value

    @property
    def x(self):
        return self.payload[3]

    @x.setter
    def x(self, value):
        self.payload[3] = value

    @property
    def y(self):
        return self.payload[4]

    @y.setter
    def y(self, value):
        self.payload[4] = value

    @property
    def width(self):
        return self.payload[5]

    @width.setter
    def width(self, value):
        self.payload[5] = value

    @property
    def duration(self):
        return struct.unpack("<I", self.payload[6:10])[0] / 1000

    @duration.setter
    def duration(self, value):
        self.payload[6:10] = struct.pack("<I", int(value * 1000))

    @property
    def colors(self):
        colors = []
        for i in range(64):
            colors.append(PacketPacking.unpack(Color, self.payload[10 + i * 8 : 18 + i * 8]))
        return colors

    @colors.setter
    def colors(self, colors):
        for i, color in enumerate(colors):
            fields = color.cache_key

            c = ColorCache.get(fields)

            if not c:
                h = min([max(0, color.hue), 0xFFFF])
                s = min([max(0, color.saturation), 0xFFFF])
                b = min([max(0, color.brightness), 0xFFFF])
                k = min([max(0, color.kelvin), 0xFFFF])
                c = struct.pack("<HHHH", int(65535 * (h / 360)), int(65535 * s), int(65535 * b), k)
                ColorCache[fields] = c

            self.payload[10 + i * 8 : 18 + i * 8] = c


__all__ = ["Set64"]
