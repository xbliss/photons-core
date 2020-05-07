from photons_canvas.animations.infrastructure.events import AnimationEvent
from photons_canvas.coords import Rearranger

from photons_app import helpers as hp

import logging
import asyncio

log = logging.getLogger("photons_canvas.animations.infrastructure.animation")


class Animation:
    every = 0.075
    retries = False
    duration = 0
    num_seconds = None
    message_timeout = 0.3
    skip_background = False
    random_orientations = False
    skip_next_transition = False

    coords_separate = False
    coords_straight = False
    coords_vertically_aligned = False

    overridable = [
        "every",
        "retries",
        "duration",
        "num_seconds",
        "message_timeout",
        "skip_background",
        "random_orientations",
        "skip_next_transition",
    ]

    def __init__(self, options):
        self.options = options
        self.setup()

    @hp.memoized_property
    def ticker(self):
        return hp.ATicker(self.every, max_time=self.num_seconds)

    async def stream(self, final_future, animation_state):
        stop_fut = hp.ChildOfFuture(final_future)

        async def tick():
            async for result in self.ticker:
                yield result

        def errors(e):
            if not isinstance(e, asyncio.CancelledError):
                log.error(hp.lc(error=e, error_type=type(e)))

        async with hp.ResultStreamer(
            stop_fut, error_catcher=errors, exceptions_only_to_error_catcher=True
        ) as streamer:
            await streamer.add_generator(tick(), context=AnimationEvent.Types.TICK)
            await streamer.add_generator(
                self.make_user_events(animation_state), context=AnimationEvent.Types.USER_EVENT
            )
            streamer.no_more_work()

            async for result in streamer:
                if result.value is hp.ResultStreamer.GeneratorComplete:
                    continue
                yield result

    def setup(self):
        pass

    @property
    def rearranger(self):
        return Rearranger(
            coords_separate=self.coords_separate,
            coords_straight=self.coords_straight,
            coords_vertically_aligned=self.coords_vertically_aligned,
        )

    async def process_event(self, event):
        raise NotImplementedError()

    async def make_user_events(self, animation_state):
        if False:
            yield

    def __setattr__(self, key, value):
        if key == "every":
            self.change_every(value)
        else:
            super().__setattr__(key, value)

    def change_every(self, every):
        object.__setattr__(self, "every", every)
        self.ticker.change_after(self.every, set_new_every=True)
