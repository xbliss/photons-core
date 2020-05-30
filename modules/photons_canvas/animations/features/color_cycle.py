# @an_animation("color_cycle", Options)
# class TileColorCycleAnimation(Animation):
#     """Cycle through the colours"""
#
#     def setup(self):
#         self.i = 0
#
#     async def process_event(self, event):
#         if event.is_tick:
#             self.i += 1
#             self.i = self.i % 360
#             return lambda point, canvas, parts: (self.i, 1, 1, 3500)
