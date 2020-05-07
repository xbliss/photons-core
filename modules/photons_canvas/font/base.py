from photons_canvas import Coord

from textwrap import dedent


def Space(width):
    return Character("_" * width)


def character_color_func(characters, fill_color):
    def get_color(x, y):
        start = 0

        char = None
        for character in characters:
            if start + character.width > x:
                char = character
                break
            else:
                start += character.width

        if not char:
            return

        return char.color(x - start, y, fill_color)

    return get_color


def put_characters_on_canvas(canvas, characters, coords, fill_color=None, modify_point=None):
    if not characters:
        return

    (left_x, _), (top_y, _), _ = coords.bounds
    width = sum([character.width for character in characters])
    height = max([character.height for character in characters])

    canvas.set_all_points_for_coord(
        Coord.simple(left_x, top_y, width, height),
        character_color_func(characters, fill_color),
        modify_point=modify_point,
    )


class Character:
    colors = {}

    def __init__(self, char):
        char = dedent(char).strip()
        self.rows = char.split("\n")
        self.width = max([0, *[len(r) for r in self.rows]])
        self.height = len(self.rows)

    def color(self, x, y, fill_color):
        if y >= self.height:
            return

        row = self.rows[y]

        if x >= len(row):
            return

        pixel = row[x]
        if pixel == "#":
            return fill_color
        elif pixel in self.colors:
            return self.colors[pixel]
