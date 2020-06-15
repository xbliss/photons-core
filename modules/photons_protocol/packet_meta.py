from photons_protocol.fields import (
    FieldInfo,
    MultipleInfo,
    ClassInfo,
    packet_spec,
    UnboundBytes,
    FieldList,
)
from photons_protocol.errors import BadConversion

from photons_app.errors import ProgrammerError
from delfick_project.norms import dictobj


class PacketMeta:
    """
    Meta information for a packet
    """

    multi = None
    parent = None
    belongs_to = NotImplemented

    def __init__(self, classname, baseclasses, attrs):
        self.belongs_to_name = classname

        fields = attrs.get("fields")
        if fields is None:
            for kls in baseclasses:
                if hasattr(kls, "Meta") and hasattr(kls.Meta, "original_fields"):
                    fields = kls.Meta.original_fields

        if fields is None:
            msg = "PacketSpecMixin expects a fields attribute on the class or a PacketSpec parent"
            raise ProgrammerError(f"{msg}\tcreating={classname}")

        if type(fields) is dict:
            msg = "PacketSpecMixin expect fields to be a list of tuples, not a dictionary"
            raise ProgrammerError(f"{msg}\tcreating={classname}")

        resolved_fields = []

        for name, typ in fields:
            resolved = typ
            if isinstance(typ, str):
                resolved = attrs[typ]

            dynamic = False
            if isinstance(typ, str) and hasattr(resolved, "Meta") and not resolved.Meta.fields:
                dynamic = True

            resolved_fields.append((name, resolved, dynamic))

        self.fields = resolved_fields
        self.fields_dict = dict([(n, (t, d)) for n, t, d in resolved_fields])
        self.all_names = self._find_all_names()
        self.name_to_group = self._find_name_to_group()

        duplicated = [name for name in self.all_names if self.all_names.count(name) > 1]
        if duplicated:
            raise ProgrammerError("Duplicated names!\t{0}".format(duplicated))

    def __repr__(self):
        return f"<type {self.belongs_to_name}.Meta>"

    def _find_all_names(self):
        all_names = []

        for name, typ, _ in self.fields:
            if hasattr(typ, "Meta"):
                all_names.extend(typ.Meta.all_names)
            else:
                all_names.append(name)

        return all_names

    def _find_name_to_group(self):
        name_to_group = {}
        for name, typ, _ in self.fields:
            if hasattr(typ, "Meta"):
                for field in typ.Meta.all_names:
                    name_to_group[field] = name

        if self.parent:
            name_to_group.update(self.parent.Meta.name_to_group)

        return name_to_group

    def size_bits(self, pkt):
        total = 0
        for name, typ, _ in self.fields:
            if hasattr(typ, "Meta"):
                total += typ.Meta.size_bits(pkt)
            else:
                total += typ.total_size_bits(pkt)

        return total

    def spec(self):
        """
        Return an ``delfick_project.norms`` specification that creates an instance
        of this class from a dictionary of values
        """
        return packet_spec(self.belongs_to())

    def actual(self, pkt, field):
        if field not in self.field_names:
            raise KeyError(field)
        return dictobj.__getitem__(pkt, field)

    def simplify(self, pkt):
        if not self.parent:
            return pkt

        final = self.parent()

        for field in final.fields:
            try:
                pkt.fields[field.name].transfer_onto(field, fill=True)
            except BadConversion:
                pkt.fields[field.name].transfer_onto(field)

        return final

    def make_field_infos(self, pkt, args, kwargs, fields):
        vals = {}
        for v, (n, _, _) in zip(args, self.fields):
            vals[n] = v
        vals.update(kwargs)

        self.add_field_infos(pkt, fields)

        if hasattr(vals, "fields_and_groups"):
            items = [(name, vals[name]) for name in vals.groups_and_fields()]
        else:
            items = vals.items()

        for n, v in items:
            if n in fields and getattr(v, "has_value", True):
                fields[n].transformed_val = v

        return fields

    def add_field_infos(self, pkt, fields):
        for name, typ, dynamic in self.fields:
            if dynamic:
                fields.add(FieldInfo(pkt, name, UnboundBytes, None))
                continue

            if hasattr(typ, "Meta"):
                for n, t, d in typ.Meta.fields:
                    fields.add(FieldInfo(pkt, n, t, name))
                fields.add((pkt, name, typ))
            else:
                count = typ.multiple_count
                if count > 0:
                    fields.add(self.multiple_field(pkt, name, typ, count))
                else:
                    fields.add(self.a_field(pkt, name, typ))

    def multiple_field(self, pkt, name, typ, count):
        lst = FieldList(pkt)

        for i in range(count):
            lst.add(self.a_field(pkt, i, typ))

        return MultipleInfo(pkt, name, lst, self.name_to_group.get(name))

    def a_field(self, pkt, name, typ):
        combined_kls = typ.combined
        group = self.name_to_group.get(name)

        if combined_kls:
            return ClassInfo(pkt, name, group, combined_kls)
        else:
            return FieldInfo(pkt, name, typ, group)
