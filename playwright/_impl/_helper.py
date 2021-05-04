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

import fnmatch
import math
import os
import re
import sys
import time
import traceback
from pathlib import Path
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Union,
    cast,
)

from playwright._impl._api_types import Error, TimeoutError

if sys.version_info >= (3, 8):  # pragma: no cover
    from typing import Literal, TypedDict
else:  # pragma: no cover
    from typing_extensions import Literal, TypedDict


if TYPE_CHECKING:  # pragma: no cover
    from playwright._impl._network import Request, Response, Route

URLMatch = Union[str, Pattern, Callable[[str], bool]]
URLMatchRequest = Union[str, Pattern, Callable[["Request"], bool]]
URLMatchResponse = Union[str, Pattern, Callable[["Response"], bool]]
RouteHandler = Union[Callable[["Route"], Any], Callable[["Route", "Request"], Any]]

ColorScheme = Literal["dark", "light", "no-preference"]
DocumentLoadState = Literal["domcontentloaded", "load", "networkidle"]
KeyboardModifier = Literal["Alt", "Control", "Meta", "Shift"]
MouseButton = Literal["left", "middle", "right"]

BrowserChannel = Literal[
    "chrome",
    "chrome-beta",
    "chrome-canary",
    "chrome-dev",
    "firefox-stable",
    "msedge",
    "msedge-beta",
    "msedge-canary",
    "msedge-dev",
]


class ErrorPayload(TypedDict, total=False):
    message: str
    name: str
    stack: str
    value: Any


class Header(TypedDict):
    name: str
    value: str


class ContinueParameters(TypedDict, total=False):
    url: Optional[str]
    method: Optional[str]
    headers: Optional[List[Header]]
    postData: Optional[str]


class ParsedMessageParams(TypedDict):
    type: str
    guid: str
    initializer: Dict


class ParsedMessagePayload(TypedDict, total=False):
    id: int
    guid: str
    method: str
    params: ParsedMessageParams
    result: Any
    error: ErrorPayload


class Document(TypedDict):
    request: Optional[Any]


class FrameNavigatedEvent(TypedDict):
    url: str
    name: str
    newDocument: Optional[Document]
    error: Optional[str]


Env = Dict[str, Union[str, float, bool]]


class URLMatcher:
    def __init__(self, match: URLMatch) -> None:
        self._callback: Optional[Callable[[str], bool]] = None
        self._regex_obj: Optional[Pattern] = None
        if isinstance(match, str):
            regex = fnmatch.translate(match)
            self._regex_obj = re.compile(regex)
        elif isinstance(match, Pattern):
            self._regex_obj = match
        else:
            self._callback = match
        self.match = match

    def matches(self, url: str) -> bool:
        if self._callback:
            return self._callback(url)
        if self._regex_obj:
            return cast(bool, self._regex_obj.search(url))
        return False


class TimeoutSettings:
    def __init__(self, parent: Optional["TimeoutSettings"]) -> None:
        self._parent = parent
        self._timeout = 30000.0
        self._navigation_timeout = 30000.0

    def set_timeout(self, timeout: float) -> None:
        self._timeout = timeout

    def timeout(self) -> float:
        if self._timeout is not None:
            return self._timeout
        if self._parent:
            return self._parent.timeout()
        return 30000

    def set_navigation_timeout(self, navigation_timeout: float) -> None:
        self._navigation_timeout = navigation_timeout

    def navigation_timeout(self) -> float:
        if self._navigation_timeout is not None:
            return self._navigation_timeout
        if self._parent:
            return self._parent.navigation_timeout()
        return 30000


def serialize_error(ex: Exception, tb: Optional[TracebackType]) -> ErrorPayload:
    return dict(message=str(ex), name="Error", stack="".join(traceback.format_tb(tb)))


def parse_error(error: ErrorPayload) -> Error:
    base_error_class = Error
    if error.get("name") == "TimeoutError":
        base_error_class = TimeoutError
    exc = base_error_class(cast(str, patch_error_message(error.get("message"))))
    exc.name = error["name"]
    exc.stack = error["stack"]
    return exc


def patch_error_message(message: Optional[str]) -> Optional[str]:
    if message is None:
        return None

    match = re.match(r"(\w+)(: expected .*)", message)
    if match:
        message = to_snake_case(match.group(1)) + match.group(2)
    message = message.replace(
        "Pass { acceptDownloads: true }", "Pass { accept_downloads: True }"
    )
    return message


def locals_to_params(args: Dict) -> Dict:
    copy = {}
    for key in args:
        if key == "self":
            continue
        if args[key] is not None:
            copy[key] = args[key]
    return copy


def monotonic_time() -> int:
    return math.floor(time.monotonic() * 1000)


class RouteHandlerEntry:
    def __init__(self, matcher: URLMatcher, handler: RouteHandler):
        self.matcher = matcher
        self.handler = handler


def is_safe_close_error(error: Exception) -> bool:
    message = str(error)
    return message.endswith("Browser has been closed") or message.endswith(
        "Target page, context or browser has been closed"
    )


def not_installed_error(message: str) -> Exception:
    return Error(
        f"""
================================================================================
{message}
Please complete Playwright installation via running

    "python -m playwright install"

================================================================================
"""
    )


to_snake_case_regex = re.compile("((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")


def to_snake_case(name: str) -> str:
    return to_snake_case_regex.sub(r"_\1", name).lower()


def make_dirs_for_file(path: Union[Path, str]) -> None:
    if not os.path.isabs(path):
        path = Path.cwd() / path
    os.makedirs(os.path.dirname(path), exist_ok=True)
