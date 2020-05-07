from delfick_project.addons import addon_hook


__shortdesc__ = "Represent colors on devices on a plane"


@addon_hook(
    extras=[
        ("lifx.photons", "products"),
        ("lifx.photons", "messages"),
        ("lifx.photons", "control"),
    ]
)
def __lifx__(collector, *args, **kwargs):
    __import__("photons_canvas.animations.addon")
    __import__("photons_canvas.themes.addon")
