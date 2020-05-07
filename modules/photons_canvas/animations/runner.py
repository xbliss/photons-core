from photons_canvas.animations.infrastructure.device import State, AnimationDevice
from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.animations.run_options import make_run_options
from photons_canvas.animations.infrastructure import cannons

from photons_app.special import SpecialReference
from photons_app.errors import FoundNoDevices
from photons_app import helpers as hp

from photons_messages import LightMessages
from photons_products import Products

import logging
import asyncio

log = logging.getLogger("photons_canvas.animations.runner")


class AnimationRunner:
    def __init__(
        self,
        sender,
        reference,
        run_options,
        *,
        final_future,
        known_serials=None,
        animation_options=None,
        **kwargs
    ):
        self.sender = sender
        self.kwargs = kwargs
        self.reference = reference
        self.run_options = make_run_options(run_options, animation_options)
        self.final_future = hp.ChildOfFuture(final_future)
        self.known_serials = known_serials

        self.collected = {}

        if self.known_serials is None:
            self.known_serials = set()

    def make_cannon(self):
        if not self.run_options.noisy_network:
            return cannons.FastNetworkCannon(self.sender, cannons.Sem())
        else:
            sem = cannons.Sem(
                wait_timeout=self.kwargs.get("message_timeout", 1),
                inflight_limit=self.run_options.noisy_network,
            )
            return cannons.NoisyNetworkCannon(self.sender, sem)

    async def run(self):
        cannon = self.make_cannon()

        animations = self.run_options.animations_iter

        async with self.reinstate(), hp.TaskHolder(self.final_future) as ts:
            combined_state = State(self.final_future)
            self.transfer_error(ts, ts.add(self.animate(ts, cannon, combined_state, animations)))

            async for results in self.collect_devices(ts):
                try:
                    if self.run_options.combined:
                        for device, chain in results:
                            await combined_state.add_device(device, chain)
                    else:
                        for device, chain in results:
                            state = State(self.final_future)
                            await state.add_device(device, chain)
                            self.transfer_error(
                                ts, ts.add(self.animate(ts, cannon, state, animations)),
                            )
                except asyncio.CancelledError:
                    raise
                except Finish:
                    pass
                except Exception as error:
                    log.exception(hp.lc("Failed to add device", error=error))

    def transfer_error(self, ts, t):
        def process(res, fut):
            if ts.pending == 0:
                fut.cancel()

        try:
            t.add_done_callback(
                hp.transfer_result(self.final_future, errors_only=True, process=process)
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self.final_future.done():
                self.final_future.set_exception(error)

    async def animate(self, ts, cannon, state, animations):
        ans = iter(animations())
        animation = None

        while True:
            try:
                make_animation, background = ans.send(animation)
            except StopIteration:
                break

            animation = make_animation()
            state.set_animation(animation, background)

            async for messages in state.messages():
                for serial, msgs in messages:
                    ts.add(cannon.fire(ts, serial, msgs))

    async def collect_devices(self, ts):
        async for _ in hp.tick(self.run_options.rediscover_every, final_future=self.final_future):
            with hp.just_log_exceptions(log, reraise=[asyncio.CancelledError]):
                serials = self.reference
                if isinstance(serials, str):
                    serials = [serials]
                elif isinstance(serials, SpecialReference):
                    self.reference.reset()
                    try:
                        _, serials = await self.reference.find(
                            self.sender, timeout=self.kwargs.get("find_timeout", 10)
                        )
                    except asyncio.CancelledError:
                        raise
                    except FoundNoDevices:
                        log.warning("Didn't find any devices")
                        continue

                new = set(serials) - self.known_serials
                if not new:
                    continue

                result = []

                async for device, chain in self.devices_from_serials(new):
                    # Make sure the device isn't known by other animations currently running
                    if device.serial not in self.known_serials:
                        self.known_serials.add(device.serial)
                        self.collected[device.serial] = device
                        ts.add(self.turn_on(device.serial))
                        result.append((device, chain))

                if result:
                    yield result

    def reinstate(self):
        class CM:
            async def __aenter__(s):
                return

            async def __aexit__(s, exc_typ, exc, tb):
                if not self.run_options.reinstate_on_end:
                    return

                msgs = []
                for device in self.collected.values():
                    msgs.extend(device.reinstate_messages)
                await self.sender(msgs, message_timeout=1, errors=[])

        return CM()

    async def turn_on(self, serial):
        msg = LightMessages.SetLightPower(level=65535, duration=1)
        await self.sender(msg, serial, **self.kwargs)

    async def devices_from_serials(self, serials):
        tiles = {}
        plans = self.sender.make_plans("chain", "capability")
        async for serial, _, info in self.sender.gatherer.gather_per_serial(
            plans, serials, **self.kwargs
        ):
            if "capability" not in info or info["capability"]["product"] is not Products.LCM3_TILE:
                self.known_serials.add(serial)
                continue

            if "chain" in info:
                tiles[serial] = info["chain"]["chain"]

        if not tiles:
            return

        plans = self.sender.make_plans("colors")
        async for serial, _, colors in self.sender.gatherer.gather(
            plans, list(tiles), **self.kwargs
        ):
            device = AnimationDevice(
                serial,
                colors,
                tiles[serial],
                reinstate_duration=self.run_options.reinstate_duration,
            )
            yield device, tiles[serial]
