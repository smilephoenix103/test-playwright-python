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

from playwright.sync_api import Error, Page


def test_add_init_script_evaluate_before_anything_else_on_the_page(page):
    page.add_init_script("window.injected = 123")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_work_with_a_path(page, assetdir):
    page.add_init_script(path=assetdir / "injectedfile.js")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_work_with_content(page: Page):
    page.add_init_script("window.injected = 123")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_throw_without_path_and_content(page):
    error = None
    try:
        page.add_init_script({"foo": "bar"})
    except Error as e:
        error = e
    assert error.message == "Either path or source parameter must be specified"


def test_add_init_script_work_with_browser_context_scripts(page, context):
    context.add_init_script("window.temp = 123")
    page = context.new_page()
    page.add_init_script("window.injected = window.temp")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_work_with_browser_context_scripts_with_a_path(
    page, context, assetdir
):
    context.add_init_script(path=assetdir / "injectedfile.js")
    page = context.new_page()
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_work_with_browser_context_scripts_for_already_created_pages(
    page, context
):
    context.add_init_script("window.temp = 123")
    page.add_init_script("window.injected = window.temp")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.result") == 123


def test_add_init_script_support_multiple_scripts(page):
    page.add_init_script("window.script1 = 1")
    page.add_init_script("window.script2 = 2")
    page.goto("data:text/html,<script>window.result = window.injected</script>")
    assert page.evaluate("window.script1") == 1
    assert page.evaluate("window.script2") == 2
