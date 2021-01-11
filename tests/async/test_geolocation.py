# Copyright (c) Microsoft Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import asyncio

import pytest

from playwright.async_api import BrowserContext, Error, Page


async def test_should_work(page: Page, server, context: BrowserContext):
    await context.grant_permissions(["geolocation"])
    await page.goto(server.EMPTY_PAGE)
    await context.set_geolocation({"latitude": 10, "longitude": 10})
    geolocation = await page.evaluate(
        """() => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
      resolve({latitude: position.coords.latitude, longitude: position.coords.longitude});
    }))"""
    )
    assert geolocation == {"latitude": 10, "longitude": 10}


async def test_should_throw_when_invalid_longitude(context):
    with pytest.raises(Error) as exc:
        await context.set_geolocation({"latitude": 10, "longitude": 200})
    assert (
        "geolocation.longitude: precondition -180 <= LONGITUDE <= 180 failed."
        in exc.value.message
    )


async def test_should_isolate_contexts(page, server, context, browser):
    await context.grant_permissions(["geolocation"])
    await context.set_geolocation({"latitude": 10, "longitude": 10})
    await page.goto(server.EMPTY_PAGE)

    context2 = await browser.new_context(
        permissions=["geolocation"], geolocation={"latitude": 20, "longitude": 20}
    )

    page2 = await context2.new_page()
    await page2.goto(server.EMPTY_PAGE)

    geolocation = await page.evaluate(
        """() => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
      resolve({latitude: position.coords.latitude, longitude: position.coords.longitude})
    }))"""
    )
    assert geolocation == {"latitude": 10, "longitude": 10}

    geolocation2 = await page2.evaluate(
        """() => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
      resolve({latitude: position.coords.latitude, longitude: position.coords.longitude})
    }))"""
    )
    assert geolocation2 == {"latitude": 20, "longitude": 20}

    await context2.close()


async def test_should_use_context_options(browser, server):
    options = {
        "geolocation": {"latitude": 10, "longitude": 10},
        "permissions": ["geolocation"],
    }
    context = await browser.new_context(**options)
    page = await context.new_page()
    await page.goto(server.EMPTY_PAGE)

    geolocation = await page.evaluate(
        """() => new Promise(resolve => navigator.geolocation.getCurrentPosition(position => {
      resolve({latitude: position.coords.latitude, longitude: position.coords.longitude});
    }))"""
    )
    assert geolocation == {"latitude": 10, "longitude": 10}
    await context.close()


async def test_watchPosition_should_be_notified(page, server, context):
    await context.grant_permissions(["geolocation"])
    await page.goto(server.EMPTY_PAGE)
    messages = []
    page.on("console", lambda message: messages.append(message.text))

    await context.set_geolocation({"latitude": 0, "longitude": 0})
    await page.evaluate(
        """() => {
      navigator.geolocation.watchPosition(pos => {
        const coords = pos.coords;
        console.log(`lat=${coords.latitude} lng=${coords.longitude}`);
      }, err => {});
    }"""
    )

    await context.set_geolocation({"latitude": 0, "longitude": 10})
    await page.wait_for_event("console", lambda message: "lat=0 lng=10" in message.text)
    await context.set_geolocation({"latitude": 20, "longitude": 30})
    await page.wait_for_event(
        "console", lambda message: "lat=20 lng=30" in message.text
    )
    await context.set_geolocation({"latitude": 40, "longitude": 50})
    await page.wait_for_event(
        "console", lambda message: "lat=40 lng=50" in message.text
    )

    allMessages = "|".join(messages)
    "latitude=0 lng=10" in allMessages
    "latitude=20 lng=30" in allMessages
    "latitude=40 lng=50" in allMessages


async def test_should_use_context_options_for_popup(page, context, server):
    await context.grant_permissions(["geolocation"])
    await context.set_geolocation({"latitude": 10, "longitude": 10})
    [popup, _] = await asyncio.gather(
        page.wait_for_event("popup"),
        page.evaluate(
            "url => window._popup = window.open(url)",
            server.PREFIX + "/geolocation.html",
        ),
    )
    await popup.wait_for_load_state()
    geolocation = await popup.evaluate("() => window.geolocationPromise")
    assert geolocation == {"latitude": 10, "longitude": 10}
