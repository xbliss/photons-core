from photons_canvas.points.canvas import Canvas


class Separate:
    def rearrange(self, canvas):
        user_x = 0
        for part in canvas.parts:
            yield part, part.real_part.clone(user_x=user_x)
            user_x += part.width / 8


class Straight:
    def rearrange(self, canvas):
        user_x = 0
        for part in sorted(
            canvas.parts, key=lambda p: (p.real_part.user_x, p.device, p.part_number)
        ):
            yield part, part.real_part.clone(user_x=user_x, user_y=0)
            user_x += part.width / 8


class VerticalAlignment:
    def rearrange(self, canvas):
        for part in canvas.parts:
            yield part, part.real_part.clone(user_y=0)


def rearrange(canvas, rearranger, keep_colors=True):
    new = Canvas()

    parts = []

    for old_part, new_part in rearranger.rearrange(canvas):
        if keep_colors:
            parts.append((new_part, [canvas[p] for p in old_part.points]))
        else:
            parts.append(new_part)

    new.add_parts(*parts)
    return new
