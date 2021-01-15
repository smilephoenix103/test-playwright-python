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
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class EventInfoImpl(Generic[T]):
    def __init__(self, future: asyncio.Future) -> None:
        self._future = future

    @property
    async def value(self) -> T:
        return await self._future


class EventContextManagerImpl(Generic[T]):
    def __init__(self, future: asyncio.Future) -> None:
        self._event: EventInfoImpl = EventInfoImpl(future)

    @property
    def future(self) -> asyncio.Future:
        return self._event._future

    async def __aenter__(self) -> EventInfoImpl[T]:
        return self._event

    async def __aexit__(self, *args: Any) -> None:
        await self._event.value
