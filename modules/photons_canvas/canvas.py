"""
The canvas is class for storing the 2d grid of colours for tiles. The canvas is
usually the colours across multiple tiles and then the TileApplier is able to
extract each tile from the canvas

.. autoclass:: photons_canvas.Canvas
    :members:

.. autoclass:: photons_canvas.CanvasColor
"""
from photons_app.errors import PhotonsAppError
from photons_messages import TileMessages

import kdtree
import math


class GetColor:
    def __init__(self, coord):
        self.coord = coord

    def __call__(self, x, y):
        return CanvasColor(0, 0, 0, 3500)


def weighted_points(points):
    """
    Return an array of points where there is more of a point the closest it is.

    points
        An array of ``(distance, color)`` where distance is a number representing
        how far away the color is.
    """

    if not points:
        return

    greatest_distance = max(dist for dist, _ in points)

    weighted = []

    for dist, point in points:
        if dist == 0:
            weighted.append(point)
        else:
            weighted.extend([point] * int(greatest_distance / dist))

    return weighted


class CanvasColor:
    is_dict = True

    def __init__(self, hue, saturation, brightness, kelvin):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = int(kelvin)

    def clone(self):
        return CanvasColor(self.hue, self.saturation, self.brightness, self.kelvin)

    @classmethod
    def average(self, colors):
        """
        Return the average of all the provided colors

        If there are no colors we return white.
        """
        if not colors:
            return CanvasColor(0, 0, 1, 3500)

        hue_x_total = 0
        hue_y_total = 0
        saturation_total = 0
        brightness_total = 0
        kelvin_total = 0

        for color in colors:
            hue_x_total += math.sin(color.hue * 2.0 * math.pi / 360)
            hue_y_total += math.cos(color.hue * 2.0 * math.pi / 360)
            saturation_total += color.saturation
            brightness_total += color.brightness

            if color.kelvin == 0:
                kelvin_total += 3500
            else:
                kelvin_total += color.kelvin

        hue = math.atan2(hue_x_total, hue_y_total) / (2.0 * math.pi)
        if hue < 0.0:
            hue += 1.0
        hue *= 360

        number_colors = len(colors)
        saturation = saturation_total / number_colors
        brightness = brightness_total / number_colors
        kelvin = int(kelvin_total / number_colors)

        return CanvasColor(hue, saturation, brightness, kelvin)

    def limit_distance_to(self, other):
        """
        Return a color within 90 hue points of this color

        We take or add 90 depending on whether the other color is more than 180 hue points away
        where that is calculated by moving forward and wrapping around 360

        If the difference between the two colors is less than 90, then we just return the original color
        """
        raw_dist = self.hue - other.hue if self.hue > other.hue else other.hue - self.hue
        dist = 360 - raw_dist if raw_dist > 180 else raw_dist
        if abs(dist) > 90:
            h = self.hue + 90 if (other.hue + dist) % 360 == self.hue else self.hue - 90
            if h < 0:
                h += 360
            return CanvasColor(h, self.saturation, self.brightness, self.kelvin)
        else:
            return self

    @property
    def cache_key(self):
        """
        This is used by the photons_canvas.animations module to use as a key for caching
        """
        return (self.hue, self.saturation, self.brightness, self.kelvin)

    def as_dict(self):
        return {
            "hue": self.hue,
            "saturation": self.saturation,
            "brightness": self.brightness,
            "kelvin": self.kelvin,
        }

    def get(self, attr, dflt):
        if attr not in self:
            return dflt
        return getattr(self, attr)

    def __lt__(self, other):
        return self.cache_key < other.cache_key

    def __contains__(self, attr):
        return attr in ("hue", "saturation", "brightness", "kelvin")

    def __hash__(self):
        return hash(self.cache_key)

    def __repr__(self):
        return f"<Color ({self.hue}, {self.saturation}, {self.brightness}, {self.kelvin})>"


class Canvas:
    """
    This is just a collection of points with methods for interacting with those
    points.

    The points are stored as (i, j) in a dictionary. Ideally the points values
    are ``photons_canvas.canvas.CanvasColor`` objects.
    """

    def __init__(self, with_kdtree=False):
        self.points = {}
        self.kdtree = None
        if with_kdtree:
            if with_kdtree is True:
                with_kdtree = []
            self.kdtree = kdtree.create(list(with_kdtree), dimensions=2)
        self.color_func = None
        self.default_color_func = None

    def clone(self):
        canvas = Canvas()
        canvas.points = dict(self.points)
        canvas.color_func = self.color_func
        canvas.default_color_func = self.default_color_func
        return canvas

    def clone_with_kdtree(self):
        canvas = Canvas(with_kdtree=self.points)
        canvas.points = dict(self.points)
        canvas.color_func = self.color_func
        canvas.default_color_func = self.default_color_func
        return canvas

    def messages_for(
        self,
        coords,
        *,
        acks=True,
        Set64=None,
        duration=1,
        randomize=False,
        background=None,
        background_canvas=None,
    ):
        """
        Make messages that set colors on a device, given the coords in this canvas.

        We return (made_messages, made_colors)

        Where made_messages are the Set64 messages for this device
        and made_colors is a list of the colors per item in the chain.
        """
        made_colors = []
        made_messages = []

        if background is None:
            background = __import__("photons_canvas").Background()

        if Set64 is None:
            Set64 = TileMessages.Set64

        for coord in coords:
            colors = background.colors(self, background_canvas, coord)
            colors = coord.reorient(colors, randomize=randomize)

            made_colors.append((coord.chain_index, colors))

            made_messages.append(
                Set64(
                    x=0,
                    y=0,
                    length=1,
                    tile_index=coord.chain_index,
                    colors=colors,
                    ack_required=acks,
                    width=coord.width,
                    duration=duration,
                    res_required=False,
                    target=coord.serial,
                )
            )

        return made_messages, [cs for _, cs in sorted(made_colors)]

    def set_color_func(self, color_func):
        """
        Add a color func to the canvas

        This will override any points that are on the canvas
        on getting those points.
        """
        self.color_func = color_func

    def set_default_color_func(self, default_color_func):
        """
        Add a default color func to the canvas

        This will be used when getting points on the canvas that aren't filled.
        """
        self.default_color_func = default_color_func

    @property
    def center(self):
        if not self.points:
            return (0, 0)

        (left_x, right_x), (top_y, bottom_y), (width, height) = self.bounds
        return (int(width / 2) + left_x, int(height / 2) + bottom_y)

    @property
    def bounds(self):
        left_x = 0
        right_x = 0

        top_y = 0
        bottom_y = 0

        for point in self.points:
            if point[0] < left_x:
                left_x = point[0]

            if point[0] > right_x:
                right_x = point[0]

            if point[1] > top_y:
                top_y = point[1]

            if point[1] < bottom_y:
                bottom_y = point[1]

        width = abs(right_x - left_x)
        height = abs(top_y - bottom_y)

        return (left_x, right_x), (top_y, bottom_y), (width, height)

    def set_all_points_for_coord(self, coord, get_color, modify_point=None):
        """
        Translates x, y points relative to a single tile to the tile position on the canvas

        So let's say a tile is at (10, 2) then get_color will be called with (x, y) from
        0 to tile_width, 0 to tile_height and those points get translated to start from (10, 2)

        NOTE: get_color gets y where higher y means moving down, whereas the coordinates on the canvas
            is higher y means moving up.

        So let's say you have a 4 by 4 tile, get_color will be called with the following points:

        .. code-block:: none

            (0, 0) (1, 0) (2, 0) (3, 0)
            (0, 1) (1, 1) (2, 1) (3, 1)
            (0, 2) (1, 2) (2, 2) (3, 2)
            (0, 3) (1, 3) (2, 3) (3, 3)

        And if you have left_x, top_y of (10, 4), it'll set the following points on the canvas:

        .. code-block:: none

            (10, 4) (11, 4) (12, 4) (13, 4)
            (10, 3) (11, 3) (12, 3) (13, 3)
            (10, 2) (11, 2) (12, 2) (13, 2)
            (10, 1) (11, 1) (12, 1) (13, 1)

        if get_color returns None, then no point is set for that turn
        """

        if isinstance(get_color, type):
            get_color = get_color(coord)

        for point in coord.points:
            x = point[0] - coord.left_x
            y = coord.top_y + coord.height - point[1]

            if getattr(get_color, "requires_coord", False):
                color = get_color(coord, x, y)
            else:
                color = get_color(x, y)

            if color is not None:
                if modify_point:
                    point = modify_point(point)
                self[point] = color

    def set_all_points_for_coords(self, coords, get_color, modify_point=None):
        for coord in coords:
            self.set_all_points_for_coord(coord, get_color, modify_point=modify_point)

    def has_neighbour(self, point):
        """Return whether there are any points around this (i, j) position"""
        return any(self.surrounding_points(point))

    def points_for_coord(self, coord):
        """
        Return a list of 64 hsbk values for this tile

        For any point on the tile that doesn't have a corresponding point on the
        canvas return a grey value. This is useful for when we tell the applier
        to not fill in the gaps.
        """
        result = []
        grey = CanvasColor(0, 0, 0.3, 3500)

        for point in coord.points:
            result.append(self.get(point, grey))

        return result

    def filled_blur(self, coords):
        """
        Fill in the gaps on this canvas by blurring the points on the provided
        canvas around where our tile is.

        We blur by finding the 4 closest points for each point on our tile and
        averaging them.
        """
        for point in coords.all_points:
            close_points = self.closest_points(point, 2)
            self[point] = self.average(weighted_points(close_points))

    def average(self, points):
        """
        Return the average of all the provided colors

        If there are no colors we return white.
        """
        return CanvasColor.average([self[point] for point in points])

    def closest_points(self, point, consider):
        """
        Return ``[(distance, color), ...]`` for ``consider`` closest points to (i, j)
        """
        if not self.kdtree:
            raise PhotonsAppError(
                "closest_points is only available when the canvas is created with with_kdtree=True"
            )

        if not self.points:
            return []

        return [(dist, node.data) for node, dist in self.kdtree.search_knn(point, consider)]

    def surrounding_points(self, point, all_points=False):
        """Return the co-ordinates that are neighbours of this point"""
        i, j = point

        return [
            point
            for point in (
                (i - 1, j + 1),
                (i, j + 1),
                (i + 1, j + 1),
                (i - 1, j),
                (i + 1, j),
                (i - 1, j - 1),
                (i, j - 1),
                (i + 1, j - 1),
            )
            if all_points or point in self.points
        ]

    def __iter__(self):
        """Yield ``((i, j), color)`` pairs for all our points"""
        return iter(self.points.items())

    def __len__(self):
        """Return how many points are in the canvas"""
        return len(self.points)

    def __bool__(self):
        return bool(len(self) > 0 or self.color_func or self.default_color_func)

    def get(self, point, dflt=None):
        """
        Get a point or the passed in ``dflt`` value if the point doesn't exist

        If this canvas has a default_color_func then dflt is ignored and the
        default_color_func is used instead
        """
        if self.color_func:
            return self.color_func(*point)
        if point not in self.points and self.default_color_func:
            return self.default_color_func(*point)
        return self.points.get(point, dflt)

    def __getitem__(self, point):
        """Return the color at ``point`` where ``point`` is ``(i, j)``"""
        if self.color_func:
            return self.color_func(*point)
        if point not in self.points and self.default_color_func:
            return self.default_color_func(*point)
        return self.points[point]

    def __setitem__(self, point, color):
        """Set the color at ``point`` where ``point`` is ``(i, j)``"""
        self.points[point] = color
        if self.kdtree:
            self.kdtree.add(point)

    def __delitem__(self, point):
        """Remove a point from our points"""
        del self.points[point]
        if self.kdtree:
            self.kdtree.remove(point)

    def __contains__(self, point):
        """Return whether this ``point`` has a color where ``point`` is ``(i, j)``"""
        return point in self.points
