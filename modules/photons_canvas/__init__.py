"""
This module contains code for representing the colors for devices on a plane
that covers one or more devices.

Tasks
-----

See :ref:`tasks`.

.. photons_module_tasks::

Themes
------

.. automodule:: photons_canvas.theme

Canvas
------

.. automodule:: photons_canvas.canvas

Animations
----------

.. automodule:: photons_canvas.animations
"""

from photons_canvas.backgrounds import Background, background_spec
from photons_canvas.canvas import Canvas, CanvasColor, GetColor
from photons_canvas.coords import Coords, Rearranger, Coord
from photons_canvas.themes import ApplyTheme

__all__ = [
    "Coord",
    "Canvas",
    "Coords",
    "GetColor",
    "Rearranger",
    "ApplyTheme",
    "Background",
    "CanvasColor",
    "background_spec",
]
