from bitarray import bitarray
import binascii
import json


class PacketReprEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) is bytes:
            return binascii.hexlify(o).decode()
        elif type(o) is bitarray:
            return binascii.hexlify(o.tobytes()).decode()
        else:
            return repr(o)

    def normalise(self, o):
        if hasattr(o, "as_dict"):
            return self.normalise(o.as_dict())
        elif isinstance(o, list):
            return [self.normalise(item) for item in o]
        elif isinstance(o, dict):
            return {k: self.normalise(v) for k, v in o.items()}
        else:
            return o

    def encode(self, o):
        return super().encode(self.normalise(o))


packet_encoder = PacketReprEncoder()
