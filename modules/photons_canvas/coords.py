from photons_app import helpers as hp

from photons_control.orientation import (
    nearest_orientation,
    Orientation,
    reverse_orientation,
    reorient,
)

from delfick_project.norms import dictobj
from collections import defaultdict
import random


class Bounds(dictobj):
    fields = ["left_x", "right_x", "top_y", "bottom_y", "width", "height"]

    def __iter__(self):
        yield from (
            (self.left_x, self.right_x),
            (self.top_y, self.bottom_y),
            (self.width, self.height),
        )


def bounds(coords):
    if not coords:
        return Bounds(0, 0, 0, 0, 0, 0)

    left_x = None
    right_x = None

    top_y = None
    bottom_y = None

    for coord in coords:
        if left_x is None or coord.left_x < left_x:
            left_x = coord.left_x

        rx = coord.left_x + coord.width
        if right_x is None or rx > right_x:
            right_x = rx

        if top_y is None or coord.top_y < top_y:
            top_y = coord.top_y

        by = coord.top_y + coord.height
        if bottom_y is None or by > bottom_y:
            bottom_y = by

    width = abs(right_x - left_x)
    height = abs(bottom_y - top_y)

    return Bounds(left_x, right_x, top_y, bottom_y, width, height)


class Rearranger:
    coords_separate = False
    coords_straight = False
    coords_vertically_aligned = False

    def __init__(self, coords_separate=None, coords_straight=None, coords_vertically_aligned=None):
        if coords_separate is not None:
            self.coords_separate = coords_separate
        if coords_straight is not None:
            self.coords_straight = coords_straight
        if coords_vertically_aligned is not None:
            self.coords_vertically_aligned = coords_vertically_aligned

    def rearrange(self, coords):
        if self.coords_vertically_aligned:
            self.align_vertically(coords)

        elif self.coords_separate or self.coords_straight:
            self.align_horizontally(coords)

    def align_vertically(self, coords):
        def rearrange(device_coords):
            for coord in device_coords:
                yield coord.clone(top_y=0)

        coords.rearrange_each(rearrange)

    def align_horizontally(self, coords):
        all_coords = []
        for serial in coords.order:
            all_coords.extend(sorted(coords.for_serial(serial)))

        rearranged = defaultdict(list)

        start = 0

        for coord in all_coords:
            top_y = 0 if self.coords_straight else coord.top_y
            rearranged[coord.serial].append(coord.clone(left_x=start, top_y=top_y))
            start += coord.width

        def rearrange(device_coords):
            yield from rearranged[device_coords.serial]

        coords.rearrange_each(rearrange)


class Coords:
    def __init__(self):
        self.by_device = {}
        self.order = []

    def clone(self):
        coords = Coords()
        for serial, device_coords in self.by_device.items():
            coords.by_device[serial] = device_coords.clone()
        coords.order = list(self.order)
        return coords

    @property
    def rearranger(self):
        return getattr(self, "_rearranger", None)

    @rearranger.setter
    def rearranger(self, rearranger):
        self._rearranger = rearranger
        self._rearrange()

    def _rearrange(self):
        if self.rearranger:
            self.rearranger.rearrange(self)

    def add_device(self, serial, chain):
        self.order.append(serial)
        device_coords = DeviceCoords.from_chain(serial, chain)
        self.by_device[serial] = device_coords
        self._rearrange()
        return self.by_device[serial]

    def steal_coords(self, coords):
        self.by_device.update(coords.by_device)
        self._rearrange()

    @property
    def all_points(self):
        for coord in self:
            for j in range(coord.top_y + coord.height, coord.top_y, -1):
                for i in range(coord.left_x, coord.left_x + coord.width):
                    yield (i, j)

    def rearrange_each(self, rearranger):
        for serial, device_coords in self.by_device.items():
            self.by_device[serial].coords = list(rearranger(device_coords))

    def change_device(self, serial, coords):
        self.by_device[serial] = DeviceCoords(serial, coords)

    def for_serial(self, serial):
        return self.by_device[serial]

    def has_serial(self, serial):
        return serial in self.by_device

    @property
    def bounds(self):
        return bounds(self)

    def spread_points(self, *, extra_proportion=1, spread=3):
        (left_x, right_x), (top_y, bottom_y), (width, height) = self.bounds

        if spread > 1:
            left_x -= int(width * extra_proportion)
            right_x += int(width * extra_proportion)
            top_y -= int(height * extra_proportion)
            bottom_y += int(height * extra_proportion)

        i = left_x
        while i < right_x:
            j = top_y
            while j < bottom_y:
                yield (i, j)
                j += random.choice([i + 1 for i in range(spread)])
            i += random.choice([i + 1 for i in range(spread)])

    def __iter__(self):
        for device_coords in self.by_device.values():
            for coords in device_coords:
                yield coords

    def __bool__(self):
        return bool(self.by_device)

    def __len__(self):
        count = 0
        for device_coords in self.by_device.values():
            count += len(device_coords)
        return count


class DeviceCoords:
    @classmethod
    def from_chain(self, serial, chain):
        return DeviceCoords(
            serial,
            [
                Coord.from_chain_item(serial, chain_index, item)
                for chain_index, item in enumerate(chain)
            ],
        )

    def __init__(self, serial, coords):
        self.serial = serial
        self.coords = coords

    def clone(self):
        return DeviceCoords(self.serial, [c.clone() for c in self.coords])

    def add_coord(self, coord):
        self.coords.append(coord)
        self.set_rearranged(self.coords)

    def set_rearranged(self, rearranged):
        if callable(rearranged):
            rearranged = rearranged(self)
        self.coords = list(rearranged)

    @property
    def bounds(self):
        return bounds(self)

    def __iter__(self):
        for coord in self.coords:
            yield coord

    def __len__(self):
        return len(self.coords)

    def __getitem__(self, chain_index):
        for coord in self.coords:
            if coord.chain_index == chain_index:
                return coord
        raise IndexError(chain_index)


class Coord:
    @classmethod
    def from_chain_item(kls, serial, chain_index, item):
        x = item.user_x
        y = item.user_y
        w = item.width
        h = item.height
        orientation = nearest_orientation(item.accel_meas_x, item.accel_meas_y, item.accel_meas_z)
        left_x, top_y = kls.make_left_x_top_y(x, y, w, h)
        return Coord(serial, chain_index, orientation, left_x, top_y, w, h,)

    @classmethod
    def make_left_x_top_y(kls, user_x, user_y, width, height):
        x, y, w, h = user_x, user_y, width, height
        return (int((x * w) - (w * 0.5)), int((y * h) + (h * 0.5)))

    @classmethod
    def simple(self, left_x, top_y, width, height):
        return Coord(None, 0, Orientation.RightSideUp, left_x, top_y, width, height)

    def __init__(self, serial, chain_index, orientation, left_x, top_y, width, height):
        self.serial = serial
        self.chain_index = chain_index
        self.orientation = orientation

        self.top_y = top_y
        self.width = width
        self.left_x = left_x
        self.height = height

    def replace_top_left(self, left_x, top_y):
        w, h = self.width, self.height
        self.left_x, self.top_y = left_x, top_y
        return ((left_x + (w * 0.5)) / w), ((top_y - (h * 0.5)) / h)

    @property
    def bounds(self):
        return bounds([self])

    @hp.memoized_property
    def random_orientation(self):
        return random.choice(list(Orientation.__members__.values()))

    def clone(self, left_x=None, top_y=None):
        if left_x is None:
            left_x = self.left_x
        if top_y is None:
            top_y = self.top_y
        return Coord(
            self.serial, self.chain_index, self.orientation, left_x, top_y, self.width, self.height
        )

    @property
    def points(self):
        for j in range(self.top_y + self.height, self.top_y, -1):
            for i in range(self.left_x, self.left_x + self.width):
                yield (i, j)

    def reverse_orient(self, colors):
        o = reverse_orientation(self.orientation)
        return reorient(colors, o)

    def reorient(self, colors, randomize=False):
        o = self.orientation
        if randomize:
            o = self.random_orientation
        return reorient(colors, o)

    def __iter__(self):
        yield from ((self.left_x, self.top_y), (self.width, self.height))

    def __lt__(self, other):
        return list(self) < list(other)

    def __getitem__(self, key):
        return list(self)[key]

    def __repr__(self):
        return f"<Coord ({self.left_x},{self.top_y},{self.width},{self.height})>"
