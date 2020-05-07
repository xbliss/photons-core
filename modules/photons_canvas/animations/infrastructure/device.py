from photons_canvas.animations.infrastructure.events import AnimationEvent
from photons_canvas.animations.infrastructure.simple_messages import Set64
from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.canvas import Canvas
from photons_canvas.coords import Coords

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_messages import TileMessages

from contextlib import contextmanager
import logging
import asyncio

log = logging.getLogger("photons_canvas.infrastructure.device")


class AnimationError(PhotonsAppError):
    pass


@contextmanager
def catch_finish(reraise_exceptions=True):
    try:
        yield
    except asyncio.CancelledError:
        raise
    except Finish:
        pass
    except:
        if reraise_exceptions:
            raise
        log.exception("Unexpected error")


class AnimationDevice:
    def __init__(self, serial, colors, chain, reinstate_duration=1):
        self.serial = serial
        self.colors = colors

        self.animation = None
        self.randomize = False
        self.background_canvas = None

        self.reinstate_messages = [
            TileMessages.Set64(
                target=serial,
                x=0,
                y=0,
                tile_index=i,
                width=t.width,
                colors=cs,
                length=1,
                duration=reinstate_duration,
                res_required=False,
            )
            for i, (t, cs) in enumerate(zip(chain, colors))
        ]

    def __hash__(self):
        return hash(self.serial)

    def set_animation(self, animation, background, coords, real_coords):
        if self.animation is not animation:
            self.coords = coords
            self.real_coords = real_coords

            self.animation = animation
            self.randomize = self.animation.random_orientations
            self.background_canvas = background.background_canvas(self.colors, self.coords)

    def messages_for(self, canvas, animation, background):
        made_messages, made_colors = canvas.messages_for(
            self.coords,
            duration=animation.duration,
            acks=animation.retries,
            background=background,
            background_canvas=self.background_canvas,
            Set64=Set64,
            randomize=self.randomize,
        )

        self.colors = made_colors
        return made_messages


class State:
    def __init__(self, final_future):
        self.devices = []

        self.state = None
        self.canvas = None
        self.animation = None
        self.background = None
        self.final_future = final_future

        self.coords = Coords()
        self.current_coords = Coords()

    def __bool__(self):
        return bool(self.devices)

    def ensure_error_event(self):
        class CM:
            async def __aenter__(s):
                return

            async def __aexit__(s, exc_typ, exc, tb):
                if (
                    exc is not None
                    and exc_typ is asyncio.CancelledError
                    or not isinstance(exc_typ, Exception)
                ):
                    return False

                handled = False
                if exc is not None and exc_typ is not Finish:
                    try:
                        handled = await self.process_event(AnimationEvent.Types.ERROR, exc)
                    except asyncio.CancelledError:
                        raise
                    except:
                        log.exception("Failed to process event")
                        raise Finish("Failed to process error")

                if exc_typ is not Finish and exc is not None and not handled:
                    log.exception("unhandled error", exc_info=(exc_typ, exc, tb))
                    raise Finish("Unhandled error")

        return CM()

    async def add_device(self, device, chain):
        real_coords = self.coords.add_device(device.serial, chain)
        device_coords = self.current_coords.add_device(device.serial, chain)
        self.devices.append(device)

        if self.animation:
            if self.background and not self.animation.skip_background:
                self.background.add_start(self.canvas, device.colors, device_coords)
            device.set_animation(self.animation, self.background, device_coords, real_coords)

        device.messages_for(self.canvas, self.animation, self.background)
        await self.process_event(AnimationEvent.Types.NEW_DEVICE, device)

    def set_animation(self, animation, background):
        if self.animation is not animation:
            self.canvas = Canvas()

            self.current_coords = self.coords.clone()
            self.current_coords.rearranger = animation.rearranger

            if animation.random_orientations:
                for coord in self.current_coords:
                    del coord.random_orientation

            for device in self.devices:
                device_coords = self.current_coords.for_serial(device.serial)
                real_coords = self.coords.for_serial(device.serial)

                background.add_to_canvas(self.canvas, device.colors, device_coords)
                device.set_animation(animation, background, device_coords, real_coords)

            self.state = None
            self.animation = animation
            self.background = background

    def make_all_messages(self):
        for device in self.devices:
            messages = device.messages_for(self.canvas, self.animation, self.background)
            yield device.serial, messages

    async def messages(self, device=None):
        started = False
        try:
            with catch_finish():
                await self.process_event(AnimationEvent.Types.STARTED)
                started = True

                for device in self.devices:
                    await self.process_event(AnimationEvent.Types.NEW_DEVICE, device)

                async for result in self.animation.stream(self.final_future, self):
                    async with self.ensure_error_event():
                        if not result.successful:
                            raise result.value

                        if result.context is AnimationEvent.Types.TICK:
                            if not self.devices:
                                continue
                            async for messages in self.send_canvas(
                                await self.process_event(AnimationEvent.Types.TICK)
                            ):
                                yield messages

                        else:
                            await self.process_event(result.context, result.value)
        finally:
            if not started:
                return

            with catch_finish(reraise_exceptions=False):
                await asyncio.sleep(self.animation.every)
                async for messages in self.send_canvas(
                    await self.process_event(AnimationEvent.Types.ENDED, force=True)
                ):
                    yield messages

    async def send_canvas(self, nxt):
        if nxt and not isinstance(nxt, Canvas):
            raise AnimationError(
                "process_event for a tick did not return a canvas",
                got=type(nxt),
                animation=type(self.animation),
            )

        if nxt:
            self.canvas = nxt
            messages = list(self.make_all_messages())
            yield messages

            await self.process_event(AnimationEvent.Types.SENT_MESSAGES, messages)

    async def process_event(self, typ, value=None, force=False):
        if not force and self.final_future.done():
            raise asyncio.CancelledError()

        if not self.animation:
            return

        event = AnimationEvent(typ, value, self)
        try:
            return await self.animation.process_event(event)
        except asyncio.CancelledError:
            raise
        except Finish:
            raise
        except NotImplementedError:
            log.error(
                hp.lc("Animation does not implement process_event", animation=type(self.animation))
            )
            raise Finish("Animation does not implement process_event")
        except Exception as error:
            log.exception(error)
            raise Finish("Animation failed to process event")
