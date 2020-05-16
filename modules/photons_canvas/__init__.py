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

from photons_canvas.points import helpers as point_helpers
from photons_canvas.points.containers import Point
from photons_canvas.points.canvas import Canvas
from photons_canvas.points.color import Color
from photons_canvas.theme import ApplyTheme

__all__ = ["Color", "Canvas", "Point", "point_helpers", "ApplyTheme"]
