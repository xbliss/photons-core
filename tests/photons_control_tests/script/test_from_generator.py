# coding: spec

from photons_control.test_helpers import Device, Color, ModuleLevelRunner
from photons_control.script import FromGenerator, Pipeline

from photons_app.errors import BadRun, TimedOut, BadRunWithResults
from photons_app.test_helpers import TestCase, AsyncTestCase

from photons_transport.target.errors import FailedToFindDevice
from photons_messages import DeviceMessages

from collections import defaultdict
from functools import partial
import asyncio
import time

light1 = Device("d073d5000001"
    , power = 0
    , color = Color(0, 1, 0.3, 2500)
    , use_sockets = False
    )

light2 = Device("d073d5000002"
    , power = 65535
    , color = Color(100, 1, 0.5, 2500)
    , use_sockets = False
    )

light3 = Device("d073d5000003"
    , power = 0
    , color = Color(100, 1, 0.5, 2500)
    , use_sockets = False
    )

mlr = ModuleLevelRunner([light1, light2, light3], use_sockets=False)

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "FromGenerator":
    use_default_loop = True

    async def assertScript(self, runner, gen, *, generator_kwargs=None, expected, **kwargs):
        msg = FromGenerator(gen, **(generator_kwargs or {}))
        await runner.target.script(msg).run_with_all(runner.serials, **kwargs)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

    @mlr.test
    async it "Can get results", runner:
        async def gen(reference, afr, **kwargs):
            yield DeviceMessages.GetPower(target=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
              light1: [DeviceMessages.GetPower()]
            , light2: [DeviceMessages.GetPower()]
            , light3: [DeviceMessages.GetPower()]
            }

        got = defaultdict(list)
        async for pkt, _, _ in runner.target.script(FromGenerator(gen)).run_with(runner.serials):
            got[pkt.serial].append(pkt)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

            self.assertEqual(len(got[device.serial]), 1)
            assert got[device.serial][0] | DeviceMessages.StatePower

    @mlr.test
    async it "Sends all the messages that are yielded", runner:
        async def gen(reference, afr, **kwargs):
            get_power = DeviceMessages.GetPower()

            async for pkt, _, _ in afr.transport_target.script(get_power).run_with(reference, afr, **kwargs):
                if pkt | DeviceMessages.StatePower:
                    if pkt.level == 0:
                        yield DeviceMessages.SetPower(level=65535, target=pkt.serial)
                    else:
                        yield DeviceMessages.SetPower(level=0, target=pkt.serial)

        expected = {
              light1: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=65535)]
            , light2: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=0)]
            , light3: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=65535)]
            }

        await self.assertScript(runner, gen, expected=expected)

    @mlr.test
    async it "does not ignore exception in generator", runner:
        error = Exception("NOPE")

        async def gen(reference, afr, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        with self.fuzzyAssertRaisesError(BadRun, _errors=[error]):
            await self.assertScript(runner, gen, expected=expected)

    @mlr.test
    async it "adds exception from generator to error_catcher", runner:
        got = []
        def err(e):
            got.append(e)

        error = Exception("NOPE")

        async def gen(reference, afr, **kwargs):
            raise error
            yield DeviceMessages.GetPower()

        expected = {light1: [], light2: [], light3: []}
        await self.assertScript(runner, gen, expected=expected, error_catcher=err)
        self.assertEqual(got, [error])

    @mlr.test
    async it "it can know if the message was sent successfully", runner:
        async def gen(reference, afr, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert (await t)

        expected = {
              light1: [DeviceMessages.GetPower()]
            , light2: [DeviceMessages.GetPower()]
            , light3: [DeviceMessages.GetPower()]
            }

        await self.assertScript(runner, gen
            , generator_kwargs = {"reference_override": True}
            , expected = expected
            )

    @mlr.test
    async it "it can know if the message was not sent successfully", runner:
        async def waiter(pkt):
            if pkt | DeviceMessages.GetPower:
                return False

        light1.set_received_processing(waiter)

        async def gen(reference, afr, **kwargs):
            t = yield DeviceMessages.GetPower()
            assert not (await t)

        expected = {
              light1: []
            , light2: [DeviceMessages.GetPower()]
            , light3: [DeviceMessages.GetPower()]
            }

        errors = []

        await self.assertScript(runner, gen
            , generator_kwargs = {"reference_override": True}
            , expected = expected
            , message_timeout = 0.1
            , error_catcher = errors
            )

        self.assertEqual(errors, [TimedOut("Waiting for reply to a packet", serial=light1.serial)])

    @mlr.test
    async it "it can have a serial override", runner:
        async def gen(reference, afr, **kwargs):
            async def inner_gen(level, reference, afr2, **kwargs2):
                self.assertIs(afr, afr2)
                del kwargs2["error_catcher"]
                kwargs1 = dict(kwargs)
                del kwargs1["error_catcher"]
                self.assertEqual(kwargs1, kwargs2)
                assert reference in runner.serials
                yield DeviceMessages.SetPower(level=level)

            get_power = DeviceMessages.GetPower()
            async for pkt, _, _ in afr.transport_target.script(get_power).run_with(reference, afr, **kwargs):
                if pkt.serial == light1.serial:
                    level = 1
                elif pkt.serial == light2.serial:
                    level = 2
                elif pkt.serial == light3.serial:
                    level = 3
                else:
                    assert False, f"Unknown serial: {pkt.serial}"

                yield FromGenerator(partial(inner_gen, level), reference_override=pkt.serial)

        expected = {
              light1: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=1)]
            , light2: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=2)]
            , light3: [DeviceMessages.GetPower(), DeviceMessages.SetPower(level=3)]
            }

        await self.assertScript(runner, gen
            , expected = expected
            )

    @mlr.test
    async it "it sends messages in parallel", runner:
        got = []

        async def waiter(pkt):
            if pkt | DeviceMessages.GetPower:
                got.append(time.time())
            else:
                assert false, "unknown message"

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        async def gen(reference, afr, **kwargs):
            yield DeviceMessages.GetPower(target=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
              light1: [DeviceMessages.GetPower()]
            , light2: [DeviceMessages.GetPower()]
            , light3: [DeviceMessages.GetPower()]
            }

        start = time.time()
        await self.assertScript(runner, gen, expected=expected)
        self.assertEqual(len(got), 3)
        for t in got:
            self.assertLess(t - start, 0.1)

    @mlr.test
    async it "can wait for other messages", runner:
        got = {}

        async def waiter(pkt):
            if pkt | DeviceMessages.GetPower:
                if pkt.serial not in got:
                    got[pkt.serial] = time.time()
                if pkt.serial == light2.serial:
                    return False
            else:
                assert false, "unknown message"

        light1.set_received_processing(waiter)
        light2.set_received_processing(waiter)
        light3.set_received_processing(waiter)

        async def gen(reference, afr, **kwargs):
            assert await (yield DeviceMessages.GetPower(target=light1.serial))
            assert not await (yield DeviceMessages.GetPower(target=light2.serial))
            assert await (yield DeviceMessages.GetPower(target=light3.serial))

        expected = {
              light1: [DeviceMessages.GetPower()]
            , light2: []
            , light3: [DeviceMessages.GetPower()]
            }

        start = time.time()
        errors = []
        await self.assertScript(runner, gen, expected=expected, error_catcher=errors, message_timeout=0.15)
        got = list(got.values())
        self.assertEqual(len(got), 3)
        self.assertLess(got[0] - start, 0.1)
        self.assertLess(got[1] - start, 0.1)
        self.assertGreater(got[2] - got[1], 0.1)

        self.assertEqual(errors, [TimedOut("Waiting for reply to a packet", serial=light2.serial)])

    @mlr.test
    async it "can provide errors", runner:
        async def gen(reference, afr, **kwargs):
            yield FailedToFindDevice(serial=light1.serial)
            yield DeviceMessages.GetPower(target=light2.serial)
            yield DeviceMessages.GetPower(target=light3.serial)

        expected = {
              light1: []
            , light2: [DeviceMessages.GetPower()]
            , light3: [DeviceMessages.GetPower()]
            }

        errors = []
        await self.assertScript(runner, gen, expected=expected, error_catcher=errors)
        self.assertEqual(errors, [FailedToFindDevice(serial=light1.serial)])

        with self.fuzzyAssertRaisesError(BadRunWithResults, _errors=[FailedToFindDevice(serial=light1.serial)]):
            await self.assertScript(runner, gen, expected=expected)
