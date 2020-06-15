from photons_protocol.errors import BadConversion

from delfick_project.norms import sb
from bitarray import bitarray
import binascii


class Unset:
    """Used to specify a value that has not been set"""


class OptionalRepr(type):
    def __repr__(kls):
        return "<Optional>"


class Optional(metaclass=OptionalRepr):
    pass


class unbound_bytes_spec(sb.Spec):
    def setup(self, location):
        self.location = location

    def normalise(self, meta, val):
        return ensure_bitarray(val, **self.location)


class UnboundBytes:
    is_optional = False
    has_default = False
    has_transform = False
    struct_format = None

    def __init__(self, field):
        self.pack_spec = unbound_bytes_spec(field.location)
        self.unpack_spec = self.pack_spec

    def do_pack_transform(self, pkt, value):
        return value

    def do_unpack_transform(self, pkt, value):
        return value


def ensure_bitarray(val, **extra_info):
    """Convert a bytes or bitarray value into a bitarray"""
    if val is sb.NotSpecified:
        val = b""

    if type(val) is bitarray:
        return val

    if type(val) is str:
        val = binascii.unhexlify(val.encode())

    if type(val) is not bytes:
        raise BadConversion("Couldn't get bitarray from a value", value=val, **extra_info)

    b = bitarray(endian="little")
    b.frombytes(val)
    return b
