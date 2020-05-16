from photons_canvas.theme import ApplyTheme

from photons_app.actions import an_action

from delfick_project.addons import addon_hook
import logging

log = logging.getLogger("photons_canvas.addons")


__shortdesc__ = "Represent colors on devices on a plane"


@addon_hook(
    extras=[
        ("lifx.photons", "products"),
        ("lifx.photons", "messages"),
        ("lifx.photons", "control"),
    ]
)
def __lifx__(collector, *args, **kwargs):
    return
    __import__("photons_canvas.animations.addon")


@an_action(needs_target=True, special_reference=True)
async def apply_theme(collector, target, reference, artifact, **kwargs):
    """
    Apply a theme to specified device

    ``lan:apply_theme d073d5000001 -- `{"colors": [<color>, <color>, ...], "overrides": {<hsbk dictionary>}}'``

    If you don't specify serials, then the theme will apply to all devices found
    on the network.

    Colors may be words like "red", "blue", etc. Or may be [h, s, b, k] arrays
    where each part is optional.

    You may also specify ``duration`` which is how long to take to apply in
    seconds.

    And you may also supply ``overrides`` with ``hue``, ``saturation``,
    ``brightness`` and ``kelvin`` to override the specified colors.
    """

    def errors(e):
        log.error(e)

    msg = ApplyTheme.msg(collector.photons_app.extra_as_json)
    await target.send(msg, reference, error_catcher=errors, message_timeout=2)
