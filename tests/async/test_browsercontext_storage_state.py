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
import json

import pytest


async def test_should_capture_local_storage(context, is_webkit, is_win):
    if is_webkit and is_win:
        pytest.skip()
    page1 = await context.new_page()
    await page1.route(
        "**/*", lambda route: asyncio.create_task(route.fulfill(body="<html></html>"))
    )
    await page1.goto("https://www.example.com")
    await page1.evaluate("localStorage['name1'] = 'value1'")
    await page1.goto("https://www.domain.com")
    await page1.evaluate("localStorage['name2'] = 'value2'")

    state = await context.storage_state()
    origins = state["origins"]
    assert len(origins) == 2
    assert origins[0] == {
        "origin": "https://www.example.com",
        "localStorage": [{"name": "name1", "value": "value1"}],
    }
    assert origins[1] == {
        "origin": "https://www.domain.com",
        "localStorage": [{"name": "name2", "value": "value2"}],
    }


async def test_should_set_local_storage(browser, is_webkit, is_win):
    if is_webkit and is_win:
        pytest.skip()
    context = await browser.new_context(
        storage_state={
            "origins": [
                {
                    "origin": "https://www.example.com",
                    "localStorage": [{"name": "name1", "value": "value1"}],
                }
            ]
        }
    )

    page = await context.new_page()
    await page.route(
        "**/*", lambda route: asyncio.create_task(route.fulfill(body="<html></html>"))
    )
    await page.goto("https://www.example.com")
    local_storage = await page.evaluate("window.localStorage")
    assert local_storage == {"name1": "value1"}
    await context.close()


async def test_should_round_trip_through_the_file(browser, context, tmpdir):
    page1 = await context.new_page()
    await page1.route(
        "**/*",
        lambda route: asyncio.create_task(route.fulfill(body="<html></html>")),
    )
    await page1.goto("https://www.example.com")
    await page1.evaluate(
        """() => {
            localStorage["name1"] = "value1"
            document.cookie = "username=John Doe"
            return document.cookie
        }"""
    )

    path = tmpdir / "storage-state.json"
    state = await context.storage_state(path=path)
    with open(path, "r") as f:
        written = json.load(f)
    assert state == written

    context2 = await browser.new_context(storage_state=path)
    page2 = await context2.new_page()
    await page2.route(
        "**/*",
        lambda route: asyncio.create_task(route.fulfill(body="<html></html>")),
    )
    await page2.goto("https://www.example.com")
    local_storage = await page2.evaluate("window.localStorage")
    assert local_storage == {"name1": "value1"}
    cookie = await page2.evaluate("document.cookie")
    assert cookie == "username=John Doe"
    await context2.close()
