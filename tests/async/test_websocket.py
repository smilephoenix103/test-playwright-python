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

import pytest

from playwright.async_api import Error


async def test_should_work(page, ws_server):
    value = await page.evaluate(
        """port => {
        let cb;
        const result = new Promise(f => cb = f);
        const ws = new WebSocket('ws://localhost:' + port + '/ws');
        ws.addEventListener('message', data => { ws.close(); cb(data.data); });
        return result;
    }""",
        ws_server.PORT,
    )
    assert value == "incoming"
    pass


async def test_should_emit_close_events(page, ws_server):
    async with page.expect_event("websocket") as ws_info:
        await page.evaluate(
            """port => {
            let cb;
            const result = new Promise(f => cb = f);
            const ws = new WebSocket('ws://localhost:' + port + '/ws');
            ws.addEventListener('message', data => { ws.close(); cb(data.data); });
            return result;
        }""",
            ws_server.PORT,
        )
    ws = await ws_info.value
    assert ws.url == f"ws://localhost:{ws_server.PORT}/ws"
    if not ws.is_closed():
        await ws.wait_for_event("close")
    assert ws.is_closed()


async def test_should_emit_frame_events(page, ws_server):
    sent = []
    received = []

    def on_web_socket(ws):
        ws.on("framesent", lambda payload: sent.append(payload))
        ws.on("framereceived", lambda payload: received.append(payload))

    page.on("websocket", on_web_socket)
    async with page.expect_event("websocket") as ws_info:
        await page.evaluate(
            """port => {
            const ws = new WebSocket('ws://localhost:' + port + '/ws');
            ws.addEventListener('open', () => {
                ws.send('echo-text');
            });
        }""",
            ws_server.PORT,
        )
    ws = await ws_info.value
    if not ws.is_closed():
        await ws.wait_for_event("close")

    assert sent == ["echo-text"]
    assert received == ["incoming", "text"]


async def test_should_emit_binary_frame_events(page, ws_server):
    sent = []
    received = []

    def on_web_socket(ws):
        ws.on("framesent", lambda payload: sent.append(payload))
        ws.on("framereceived", lambda payload: received.append(payload))

    page.on("websocket", on_web_socket)
    async with page.expect_event("websocket") as ws_info:
        await page.evaluate(
            """port => {
            const ws = new WebSocket('ws://localhost:' + port + '/ws');
            ws.addEventListener('open', () => {
                const binary = new Uint8Array(5);
                for (let i = 0; i < 5; ++i)
                    binary[i] = i;
                ws.send(binary);
                ws.send('echo-bin');
            });
        }""",
            ws_server.PORT,
        )
    ws = await ws_info.value
    if not ws.is_closed():
        await ws.wait_for_event("close")
    assert sent == [b"\x00\x01\x02\x03\x04", "echo-bin"]
    assert received == ["incoming", b"\x04\x02"]


@pytest.mark.skip_browser("webkit")  # Flakes on bots
async def test_should_reject_wait_for_event_on_close_and_error(page, ws_server):
    async with page.expect_event("websocket") as ws_info:
        await page.evaluate(
            """port => {
            window.ws = new WebSocket('ws://localhost:' + port + '/ws');
        }""",
            ws_server.PORT,
        )
    ws = await ws_info.value
    await ws.wait_for_event("framereceived")
    with pytest.raises(Error) as exc_info:
        async with ws.expect_event("framesent"):
            await page.evaluate("window.ws.close()")
    assert exc_info.value.message == "Socket closed"
