# Copyright (c) Microsoft Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License")
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

import http.server
import threading

import pytest
import playwright
from .server import server as server_object, HTTPRequestHandler
from .utils import utils as utils_object

# Will mark all the tests as async
def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.asyncio)

@pytest.fixture(scope='session')
def event_loop():
    loop = playwright.playwright.loop
    yield loop
    loop.close()


@pytest.fixture(scope='session')
async def browser(pytestconfig):
    browser_name = pytestconfig.getoption("browser")
    browser = await playwright.browser_types[browser_name].launch()
    yield browser
    await browser.close()


@pytest.fixture
async def context(browser):
    context = await browser.newContext()
    yield context
    await context.close()

@pytest.fixture
async def page(context):
    page = await context.newPage()
    yield page
    await page.close()

@pytest.fixture
def server():
    yield server_object

@pytest.fixture
def utils():
    yield utils_object

@pytest.fixture(autouse=True, scope='session')
async def start_http_server():
    httpd = http.server.HTTPServer(('', server_object.PORT), HTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever).start()
    yield
    httpd.shutdown()

@pytest.fixture
def browser_name(pytestconfig):
    return pytestconfig.getoption('browser')

def pytest_addoption(parser):
    group = parser.getgroup('playwright', 'Playwright')
    group.addoption(
        '--browser',
        choices=['chromium', 'firefox', 'webkit'],
        default='chromium',
        help='Browser engine which should be used',
    )


