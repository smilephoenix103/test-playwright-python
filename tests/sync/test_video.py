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

import os


def test_should_expose_video_path(browser, tmpdir, server):
    page = browser.new_page(
        record_video_dir=tmpdir, record_video_size={"width": 100, "height": 200}
    )
    page.goto(server.PREFIX + "/grid.html")
    path = page.video.path()
    assert str(tmpdir) in path
    page.context.close()


def test_video_should_exist(browser, tmpdir, server):
    page = browser.new_page(record_video_dir=tmpdir)
    page.goto(server.PREFIX + "/grid.html")
    path = page.video.path()
    assert str(tmpdir) in path
    page.context.close()
    assert os.path.exists(path)


def test_record_video_to_path(browser, tmpdir, server):
    page = browser.new_page(record_video_dir=tmpdir)
    page.goto(server.PREFIX + "/grid.html")
    path = page.video.path()
    assert str(tmpdir) in path
    page.context.close()
    assert os.path.exists(path)


def test_record_video_to_path_persistent(browser_type, tmpdir, server):
    context = browser_type.launch_persistent_context(tmpdir, record_video_dir=tmpdir)
    page = context.pages[0]
    page.goto(server.PREFIX + "/grid.html")
    path = page.video.path()
    assert str(tmpdir) in path
    context.close()
    assert os.path.exists(path)
