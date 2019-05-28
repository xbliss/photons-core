# coding: spec

from photons_app.special import SpecialReference, FoundSerials, HardCodedSerials, ResolveReferencesFromFile
from photons_app.errors import PhotonsAppError, DevicesNotFound
from photons_app.test_helpers import AsyncTestCase
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from unittest import mock
import asynctest
import binascii
import asyncio
import os

describe AsyncTestCase, "SpecialReference":
    async it "gives itself a finding and found future":
        ref = SpecialReference()
        assert isinstance(ref.finding, hp.ResettableFuture)
        assert isinstance(ref.found, hp.ResettableFuture)

    async it "can reset the futures":
        ref = SpecialReference()
        ref.finding.set_result(True)
        ref.found.set_result(True)

        assert ref.finding.done()
        assert ref.found.done()
        ref.reset()

        assert not ref.finding.done()
        assert not ref.found.done()

    describe "find":
        async before_each:
            self.afr = mock.Mock(name="afr")
            self.broadcast = mock.Mock(name="broadcast")
            self.find_timeout = mock.Mock(name="find_timeout")

        async it "transfers cancellation from find_serials":
            class Finder(SpecialReference):
                async def find_serials(s, afr, *, timeout, broadcast=True):
                    f = asyncio.Future()
                    f.cancel()
                    return await f

            ref = Finder()
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                await ref.find(self.afr, timeout=self.find_timeout)

        async it "transfers exceptions from find_serials":
            class Finder(SpecialReference):
                async def find_serials(s, afr, *, timeout, broadcast=True):
                    f = asyncio.Future()
                    f.set_exception(PhotonsAppError("FIND SERIALS BAD"))
                    return await f

            ref = Finder()
            with self.fuzzyAssertRaisesError(PhotonsAppError, "FIND SERIALS BAD"):
                await ref.find(self.afr, timeout=self.find_timeout)

        async it "transfers result from find_serials":
            serial1 = "d073d5000001"
            serial2 = "d073d5000002"

            target1 = binascii.unhexlify(serial1)
            target2 = binascii.unhexlify(serial2)

            services1 = mock.Mock(name='services1')
            services2 = mock.Mock(name="services2")

            class Finder(SpecialReference):
                async def find_serials(s, afr, *, timeout, broadcast=True):
                    return {target1: services1, target2: services2}

            ref = Finder()
            found, serials = await ref.find(self.afr, timeout=self.find_timeout)
            self.assertEqual(found, {target1: services1, target2: services2})
            self.assertEqual(serials, [serial1, serial2])

        async it "only calls find_serials once":
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            services = mock.Mock(name='services')

            called = []

            class Finder(SpecialReference):
                async def find_serials(s, afr, *, timeout, broadcast=True):
                    await asyncio.sleep(0.2)
                    called.append(1)
                    return {target: services}

            ref = Finder()
            futs = []
            futs.append(hp.async_as_background(ref.find(self.afr, timeout=self.find_timeout)))
            futs.append(hp.async_as_background(ref.find(self.afr, timeout=self.find_timeout)))
            await asyncio.sleep(0.05)
            futs.append(hp.async_as_background(ref.find(self.afr, timeout=self.find_timeout)))
            await asyncio.sleep(0.2)
            futs.append(hp.async_as_background(ref.find(self.afr, timeout=self.find_timeout)))

            for t in futs:
                found, serials = await t
                self.assertEqual(found, {target: services})
                self.assertEqual(serials, [serial])

            self.assertEqual(called, [1])

            ref.reset()
            found, serials = await ref.find(self.afr, timeout=self.find_timeout)
            self.assertEqual(found, {target: services})
            self.assertEqual(serials, [serial])
            self.assertEqual(called, [1, 1])

describe AsyncTestCase, "FoundSerials":
    async it "calls afr.find_devices with broadcast":
        found = mock.Mock(name="found")
        address = mock.Mock(name="address")

        afr = mock.Mock(name="afr")
        afr.find_devices = asynctest.mock.CoroutineMock(name="find_devices", return_value=found)

        broadcast = mock.Mock(name="broadcast")
        find_timeout = mock.Mock(name="find_timeout")

        ref = FoundSerials()
        res = await self.wait_for(ref.find_serials(afr, broadcast=broadcast, timeout=find_timeout))

        self.assertEqual(res, found)
        afr.find_devices.assert_called_once_with(broadcast=broadcast, raise_on_none=True, timeout=find_timeout)

describe AsyncTestCase, "HardCodedSerials":
    async before_each:
        self.serial1 = "d073d5000001"
        self.serial2 = "d073d5000002"

        self.target1 = binascii.unhexlify(self.serial1)[:6]
        self.target2 = binascii.unhexlify(self.serial2)[:6]

        self.info1 = mock.Mock(name="info1")
        self.info2 = mock.Mock(name="info2")

    async it "takes in a list of serials":
        serials = "d073d5000001,d073d500000200"
        wanted = [binascii.unhexlify(ref)[:6] for ref in serials.split(",")]

        for s in (serials, serials.split(",")):
            ref = HardCodedSerials(s)
            self.assertEqual(ref.targets, wanted)
            self.assertEqual(ref.serials, ["d073d5000001", "d073d5000002"])

    async it "can take in list of unhexlified serials":
        serials = [binascii.unhexlify("d073d500000100"), binascii.unhexlify("d073d5000002")]
        wanted = [binascii.unhexlify(ref)[:6] for ref in ["d073d5000001", "d073d5000002"]]

        ref = HardCodedSerials(serials)
        self.assertEqual(ref.targets, wanted)
        self.assertEqual(ref.serials, ["d073d5000001", "d073d5000002"])

    describe "find_serials":
        async def assertFindSerials(self, found, serials, expected, missing):
            broadcast = mock.Mock(name='broadcast')
            find_timeout = mock.Mock(name="find_timeout")

            afr = mock.Mock(name="afr")
            afr.found = {}
            afr.find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials")
            afr.find_specific_serials.return_value = (found, missing)

            ref = HardCodedSerials(serials)
            f = await ref.find_serials(afr, broadcast=broadcast, timeout=find_timeout)

            self.assertEqual(f, expected)

            afr.find_specific_serials.assert_called_once_with(serials
                , broadcast = broadcast
                , raise_on_none = False
                , timeout = find_timeout
                )

            self.assertEqual(ref.missing(f), missing)

        async it "uses find_specific_serials":
            found = {self.target1: self.info1, self.target2: self.info2}
            serials = [self.serial1, self.serial2]
            expected = {self.target1: self.info1, self.target2: self.info2}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async it "only returns from the serials it cares about":
            found = {self.target1: self.info1, self.target2: self.info2}
            serials = [self.serial1]
            expected = {self.target1: self.info1}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async it "doesn't call to find_specific_serials if the serials are already on the afr":
            broadcast = mock.Mock(name='broadcast')
            find_timeout = mock.Mock(name="find_timeout")

            afr = mock.Mock(name="afr")
            afr.found = {self.target1: self.info1, self.target2: self.info2}
            afr.find_specific_serials = asynctest.mock.CoroutineMock(name="find_specific_serials", side_effect=AssertionError("Shouldn't be called"))

            ref = HardCodedSerials([self.serial1])
            f = await ref.find_serials(afr, broadcast=broadcast, timeout=find_timeout)

            self.assertEqual(f, {self.target1: self.info1})
            self.assertEqual(ref.missing(f), [])

        async it "doesn't care if no found":
            found = {}
            serials = [self.serial1, self.serial2]
            expected = {}
            missing = [self.serial1, self.serial2]
            await self.assertFindSerials(found, serials, expected, missing)

        async it "can see partial missing":
            found = {self.target2: self.info2}
            serials = [self.serial1, self.serial2]
            expected = {self.target2: self.info2}
            missing = [self.serial1]
            await self.assertFindSerials(found, serials, expected, missing)

describe AsyncTestCase, "ResolveReferencesFromFile":
    async it "complains if filename can't be read or is empty":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)

            with self.fuzzyAssertRaisesError(PhotonsAppError, "Failed to read serials from a file"):
                ResolveReferencesFromFile(fle.name)

        with hp.a_temp_file() as fle:
            fle.close()
            with self.fuzzyAssertRaisesError(PhotonsAppError, "Found no serials in file"):
                ResolveReferencesFromFile(fle.name)

    async it "creates and uses a HardCodedSerials":
        serial1 = "d073d5000001"
        serial2 = "d073d5000002"

        resolver = mock.Mock(name="resolver")
        resolver.find = asynctest.mock.CoroutineMock(name="find")
        FakeHardCodedSerials = mock.Mock(name="HardCodedSerials", return_value=resolver)

        with hp.a_temp_file() as fle:
            fle.write("{}\n{}".format(serial1, serial2).encode())
            fle.close()

            with mock.patch("photons_app.special.HardCodedSerials", FakeHardCodedSerials):
                r = ResolveReferencesFromFile(fle.name)

        self.assertEqual(r.serials, [serial1, serial2])
        self.assertEqual(r.reference, resolver)
        FakeHardCodedSerials.assert_called_once_with([serial1, serial2])

        self.assertEqual(len(resolver.reset.mock_calls), 0)
        r.reset()
        resolver.reset.assert_called_once_with()

        afr = mock.Mock(name="afr")
        broadcast = mock.Mock(name='broadcast')
        find_timeout = mock.Mock(name='find_timeout')
        self.assertEqual(len(resolver.find.mock_calls), 0)

        res = mock.Mock(name="res")
        resolver.find.return_value = res
        self.assertIs(await self.wait_for(r.find(afr, timeout=find_timeout)), res)
        resolver.find.assert_called_once_with(afr, broadcast=True, timeout=find_timeout)
