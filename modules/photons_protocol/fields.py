from photons_protocol.constants import Unset, UnboundBytes, Optional, ensure_bitarray
from photons_protocol.errors import BadConversion, InvalidField
from photons_protocol.packer import PackCache, UnpackCache

from delfick_project.norms import sb, Meta
from bitarray import bitarray
import itertools


class packet_spec(sb.Spec):
    meta = Meta.empty()

    def setup(self, final):
        self.final = final

    def normalise(self, meta, val):
        final = self.final

        if val is sb.NotSpecified:
            return final

        got_identity = None
        want_identity = None
        if hasattr(final, "protocol") and hasattr(final, "pkt_type"):
            want_identity = (final.protocol, final.pkt_type)

        if isinstance(val, (bytes, bitarray, str)):
            self.fill_from_bytes(val, final)
        else:
            if not isinstance(val, (tuple, dict)):
                val = (val,)

            if isinstance(val, tuple):
                final.Meta.make_field_infos(self, val, {}, fields=final.fields)
            else:
                final.Meta.make_field_infos(self, (), val, fields=final.fields)

        if hasattr(final, "protocol") and hasattr(final, "pkt_type"):
            got_identity = (final.protocol, final.pkt_type)
            if want_identity[1] == 0:
                got_identity = (got_identity[0], 0)

        if want_identity != got_identity:
            raise BadConversion(
                "Tried to create a packet from the wrong type",
                got=got_identity,
                want=want_identity,
            )

        return final

    def fill_from_bytes(self, val, final):
        b = ensure_bitarray(val, packet=type(final).__name__)

        at = 0
        end = 0
        for field in final.fields:
            if isinstance(getattr(field, "typ", None), UnboundBytes):
                field.raw = b[at:]
                break

            end += field.size_bits
            field.raw = b[at:end]
            at = end


class FieldList:
    def __init__(self, pkt):
        self.pkt = pkt
        self.fields = []
        self.groups = []
        self.by_name = {}

    def __repr__(self):
        fields = ",".join([str(f.name) for f in self.fields])
        groups = ",".join([str(g.name) for g in self.groups])
        information = []
        if fields:
            information.append(f"fields:{fields}")
        if groups:
            information.append(f"groups:{groups}")
        return f"<FieldList {self.pkt.__class__.__name__} {' '.join(information)}>"

    def clone(self, pkt):
        clone = FieldList(pkt)
        clone.add_fields(self)
        return clone

    def is_set(self, name):
        if self[name].actual is Unset:
            return False
        return True

    def is_not_empty(self, name):
        if self.is_set(name):
            raw = self[name].raw
            return raw.count(True) > 0
        return False

    def get(self, name, dflt):
        field = self[name]
        if field.actual is Unset:
            return dflt
        return field.transformed_val

    def add(self, field):
        if isinstance(field, tuple):
            pkt, name, typ = field
            if name in self:
                return

            group_fields = FieldList(pkt)
            for field in typ.Meta.all_names:
                group_fields.add(self.by_name[field])

            field = GroupInfo(pkt, name, typ, group_fields)

            self.groups.append(field)
            self.by_name[name] = field
        else:
            if field.name in self:
                return

            if not isinstance(field, GroupInfo):
                self.fields.append(field)
            else:
                self.groups.append(field)
                self.add_fields(field.fields)

            self.by_name[field.name] = field

    def add_fields(self, fields):
        for field in fields.fields:
            if field.name not in self.by_name:
                self.add(field)

        for group in fields.groups:
            if group.name not in self.by_name:
                self.add(group)

    def __getitem__(self, name):
        return self.by_name[name]

    def __iter__(self):
        return iter(self.fields)

    def __contains__(self, name):
        return name in self.by_name

    def __eq__(self, other):
        for s, o in itertools.zip_longest(self.fields, other.fields):
            if s != o:
                return False
        return True

    def same_type(self, other):
        for s, o in itertools.zip_longest(self.fields, other.fields):
            if not s.same_type(o):
                return False

        return True


class CombinedInfo:
    title = "Combined"
    is_reserved = False

    def __init__(self, pkt, name, fields):
        self.pkt = pkt
        self.name = name
        if fields is not None:
            self.fields = fields

        self._transformed_val = Unset

        self.location = {"pkt": pkt.__class__.__name__, "field": self.name}
        self.meta = Meta({"pkt": pkt}, []).at(self.location["pkt"])

    def __repr__(self):
        return f"<{self.title} ({self.pkt.__class__.__name__},{self.name})>"

    def __iter__(self):
        return iter(self.fields)

    def __getitem__(self, key):
        return self.fields[key].transformed_val

    def __setitem__(self, key, value):
        self.fields[key].transformed_val = value

    def __eq__(self, other):
        return all(t == o for t, o in itertools.zip_longest(self, other))

    def same_type(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.name != other.name:
            return False
        return self.fields.same_type(other.fields)

    @property
    def size_bits(self):
        return sum([field.size_bits for field in self.fields])

    def make_transformed_val(self):
        raise NotImplementedError()

    @property
    def has_value(self):
        return self.actual is not Unset

    @property
    def actual(self):
        if not any(field.has_value for field in self.fields):
            return Unset

        return self.raw

    @property
    def raw(self):
        final = bitarray(endian="little")

        for field in self.fields:
            final.extend(field.raw)

        return final

    @raw.setter
    def raw(self, val):
        packet_spec(self).normalise(self.meta, val)

    @property
    def transformed_val(self):
        if self._transformed_val is Unset:
            self._transformed_val = self.make_transformed_val()
        return self._transformed_val

    @transformed_val.setter
    def transformed_val(self, values):
        if isinstance(values, bitarray):
            self.raw = values
            return

        if isinstance(values, list) or isinstance(values, MultipleInfo):
            items = zip(range(len(values)), values)
        else:
            items = values.items()

        for name, val in items:
            self.fields[name].transformed_val = val

    @property
    def untransformed_val(self):
        return self.transformed_val

    @untransformed_val.setter
    def untransformed_val(self, values):
        if isinstance(values, bitarray):
            self.raw = values
            return

        for name, val in values.items():
            self.fields[name].untransformed_val = val

    def transfer_onto(self, onto, fill=False):
        if getattr(onto, "dynamic", False):
            onto.raw = self.raw
            return

        if not self.same_type(onto):
            raise InvalidField(
                "Can only transfer one group onto another of the same type",
                source=self,
                destination=onto,
            )

        for t, o in zip(self.fields, onto.fields):
            t.transfer_onto(o, fill=fill)


class ClassInfo(CombinedInfo):
    title = "Class"
    dynamic = True

    def __init__(self, pkt, name, group, kls):
        super().__init__(pkt, name, None)
        self.group_name = group
        self._kls = kls
        self._fields = Unset

    @property
    def fields(self):
        if self._transformed_val is Unset:
            kls = self.kls
            lst = FieldList(self.pkt)
            kls.Meta.make_field_infos(self.pkt, (), {}, lst)
        else:
            lst = self._transformed_val.fields

        if self._fields is Unset or not self._fields.same_type(lst):
            self._fields = lst

        return self._fields

    @property
    def kls(self):
        if not hasattr(self._kls, "Meta"):
            return self._kls(self.pkt)
        return self._kls

    def make_transformed_val(self):
        return self.kls(fields=self.fields)


class GroupInfo(CombinedInfo):
    title = "Group"

    def __init__(self, pkt, name, group, fields):
        super().__init__(pkt, name, fields)
        self.group = group

    def make_transformed_val(self):
        return self.group(fields=self.fields)


class MultipleInfo(CombinedInfo):
    title = "Multiple"

    def __init__(self, pkt, name, fields, group_name):
        super().__init__(pkt, name, fields)
        self.group_name = group_name

    def as_dict(self):
        return list(self)

    def __len__(self):
        return len(self.fields.fields)

    def __iter__(self):
        yield from [field.transformed_val for field in self.fields]

    def make_transformed_val(self):
        return self


class FieldInfo:
    def __init__(self, pkt, name, typ, group_name):
        self.pkt = pkt
        self.name = name
        self.group_name = group_name

        self._raw = Unset
        self._transformed_val = Unset
        self._untransformed_val = Unset

        self._size_bits = Unset

        self.location = {"pkt": pkt.__class__.__name__, "field": self.name}
        self.meta = Meta({"pkt": pkt}, []).at(self.location["pkt"])

        if self.group_name:
            self.meta = self.meta.at(self.group_name)
            self.location["group"] = group_name

        self.meta = self.meta.at(self.name)

        if typ is UnboundBytes:
            typ = typ(self)

        self.typ = typ
        self.is_reserved = self.typ.__class__.__name__ == "Reserved"

        self.dynamic = group_name is None

    def __eq__(self, other):
        if not self.same_type(other):
            return False

        if self._raw is not Unset and other._raw is not Unset:
            return self._raw == other._raw

        if self._untransformed_val is not Unset and other._untransformed_val is not Unset:
            return self._untransformed_val == other._untransformed_val

        if self._transformed_val is not Unset and other._transformed_val is not Unset:
            return self._transformed_val == other._transformed_val

        return self.raw == other.raw

    def same_type(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.name != other.name:
            return False
        return self.dynamic or self.typ == other.typ

    def __repr__(self):
        return f"<Field ({self.pkt.__class__.__name__},{self.group_name},{self.name})>"

    @property
    def has_value(self):
        return self.actual is not Unset

    @property
    def size_bits(self):
        if isinstance(self.typ, UnboundBytes):
            if self._raw is Unset:
                return 0
            else:
                return len(self._raw)

        return self.typ.total_size_bits(self.pkt)

    @property
    def actual(self):
        if (
            self._transformed_val is not Unset
            or self._untransformed_val is not Unset
            or self._raw is not Unset
        ):
            return self.raw

        return Unset

    @property
    def raw(self):
        """
        Return the raw bitarray for this value.
        """
        if self._untransformed_val is Unset and self._transformed_val is not Unset:
            self._untransformed_val = self.typ.do_unpack_transform(self.pkt, self._transformed_val)

        untransformed_val = self._untransformed_val

        raw = self._raw
        if raw is Unset:
            if untransformed_val is not Unset:
                value = untransformed_val
            elif self.typ.is_optional:
                value = 0
            else:
                value = sb.NotSpecified

            if not isinstance(value, bitarray) and hasattr(value, "pack"):
                value = value.pack()

            self._raw = self.bitarray(self.typ.pack_spec.normalise(self.meta, value))

        return self._raw

    @raw.setter
    def raw(self, raw):
        raw = ensure_bitarray(raw, **self.location)
        want = self.padded_bitarray(raw, self.typ)
        if self._raw != want:
            self._raw = want
            self._transformed_val = Unset
            self._untransformed_val = Unset

    @property
    def transformed_val(self):
        if self.actual is Unset and self.typ.is_optional:
            return Optional

        if self._transformed_val is Unset:
            self._transformed_val = self.typ.do_unpack_transform(self.pkt, self.untransformed_val)

        return self._transformed_val

    @transformed_val.setter
    def transformed_val(self, val):
        if isinstance(val, bitarray):
            self.raw = val
            return

        matched = False
        if val == self._transformed_val:
            matched = True

        elif not self.typ.has_transform and val == self._untransformed_val:
            matched = True

        if not matched:
            self._transformed_val = Unset
            self._untransformed_val = self.typ.do_pack_transform(self.pkt, val)

            # Get raw set
            self._raw = Unset
            self.raw

            # And remove our untransformed value
            # It's possible converting back from raw may alter it slightly
            self._untransformed_val = Unset

    @property
    def untransformed_val(self):
        if self.actual is Unset and self.typ.is_optional:
            return Optional

        if self._untransformed_val is Unset:
            if self._transformed_val is not Unset:
                self._untransformed_val = self.typ.do_pack_transform(
                    self.pkt, self._transformed_val
                )
            else:
                self._untransformed_val = self.typ.unpack_spec.normalise(
                    self.meta, self.unpack(self.raw)
                )
        return self._untransformed_val

    @untransformed_val.setter
    def untransformed_val(self, val):
        if isinstance(val, bitarray):
            self.raw = val
            return

        matched = False
        if val == self._untransformed_val:
            matched = True

        elif not self.typ.has_transform and val == self._transformed_val:
            matched = True

        if not matched:
            self._transformed_val = Unset
            self._untransformed_val = val

            # Make sure raw is set
            self._raw = Unset
            self.raw

            # And remove our transformed value
            # It's possible converting back from raw may alter it slightly
            self._transformed_val = Unset

    def transfer_onto(self, other, fill=False):
        if other.name != self.name and other.typ != self.typ:
            raise InvalidField(
                "Cannot transfer one field onto a different field", source=self, destination=other
            )

        def clone(thing):
            if thing is Unset:
                return thing

            if hasattr(thing, "clone"):
                return thing.clone()

            if isinstance(thing, list):
                return [clone(item) for item in thing]

            return thing

        other._raw = self._raw
        other._transformed_val = clone(self._transformed_val)
        if self.typ.has_transform:
            other._transformed_val = clone(self._untransformed_val)
        else:
            other._untransformed_val = other._transformed_val

        if not self.has_value and self.typ.has_default:
            other.raw = self.raw

    def bitarray(self, val):
        result = self.unpadded_bitarray(val)

        if isinstance(self.typ, UnboundBytes):
            return result

        size_bits = self.size_bits
        if size_bits < len(result):
            if getattr(self.typ, "left_cut", False):
                result = result[-size_bits:]
            else:
                result = result[:size_bits]

        return result

    def unpadded_bitarray(self, val):
        fmt = self.typ.struct_format

        if val in (sb.NotSpecified, Unset):
            raise BadConversion("Cannot pack an unspecified value", got=val, **self.location)

        if type(val) is bitarray:
            return val

        key, hashable, val, c = PackCache.from_cache(fmt, val)

        if c is None:
            c = PackCache.convert(fmt, val, **self.location)
            if hashable:
                PackCache.set_cache(key, c)

        return c

    def unpack(self, raw):
        fmt = self.typ.struct_format

        if fmt is bool and self.size_bits == 1:
            return False if raw.to01() == "0" else True

        if fmt is None:
            return raw

        key, hashable, val, c = UnpackCache.from_cache(fmt, raw.tobytes())

        if c is None:
            c = UnpackCache.convert(fmt, val, **self.location)
            if hashable:
                UnpackCache.set_cache(key, c)

        return c

    def padded_bitarray(self, val, typ):
        if isinstance(typ, UnboundBytes):
            return val

        size_bits = typ.size_bits
        if callable(size_bits):
            size_bits = size_bits(self.pkt)

        if len(val) < size_bits:
            padding = bitarray("0" * (size_bits - len(val)), endian="little")
            if getattr(self.typ, "left_cut", False):
                val = padding + val
            else:
                val = val + padding

        return val
