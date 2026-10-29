# Copyright (c) 2026 OceanBase.
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

"""Share pending embedding work and cache successful vectors within one loop."""

from __future__ import annotations

import asyncio
import math
from collections import OrderedDict
from dataclasses import dataclass

from powercontext.builtin.inference.models import EmbeddingResult, EmbeddingVector, InferenceUsage
from powercontext.builtin.inference.protocols import EmbeddingModel, QueryEmbeddingModel


@dataclass(frozen=True, slots=True)
class _CompletedVector:
    vector: EmbeddingVector
    batch: int
    usage: InferenceUsage


class CoalescingEmbeddingModel:
    """Deduplicate queued and in-flight work without sharing caller cancellation."""

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        max_batch_size: int = 64,
        coalesce_ms: float = 5.0,
        cache_size: int = 1024,
    ) -> None:
        if type(max_batch_size) is not int or max_batch_size < 1:
            raise ValueError("max_batch_size must be a positive integer")  # noqa: TRY003
        if type(cache_size) is not int or cache_size < 0:
            raise ValueError("cache_size must be a nonnegative integer")  # noqa: TRY003
        if type(coalesce_ms) not in {int, float} or not math.isfinite(coalesce_ms) or coalesce_ms < 0:
            raise ValueError("coalesce_ms must be finite and nonnegative")  # noqa: TRY003
        self._model = model
        self.profile = model.profile
        self._batch_size = max_batch_size
        self._delay = coalesce_ms / 1000
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[bool, str], EmbeddingVector] = OrderedDict()
        self._pending: dict[tuple[bool, str], asyncio.Future[_CompletedVector]] = {}
        self._queue: OrderedDict[tuple[bool, str], asyncio.Future[_CompletedVector]] = OrderedDict()
        self._dispatcher: asyncio.Task[None] | None = None
        self._batches: set[asyncio.Task[None]] = set()
        self._batch_sequence = 0

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        return await self._embed(texts, query=False)

    async def embed_query(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        # Symmetric models share document/query cache entries. Asymmetric models
        # keep their query embeddings separate, including in-flight work.
        return await self._embed(texts, query=isinstance(self._model, QueryEmbeddingModel))

    async def _embed(self, texts: tuple[str, ...], *, query: bool) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=(), usage=InferenceUsage(requests=0))
        if any(not isinstance(text, str) for text in texts):
            raise ValueError("embedding inputs must be strings")  # noqa: TRY003
        loop = asyncio.get_running_loop()
        values: list[EmbeddingVector | asyncio.Future[_CompletedVector]] = []
        for text in texts:
            key = (query, text)
            if key in self._cache:
                self._cache.move_to_end(key)
                values.append(self._cache[key])
                continue
            future = self._pending.get(key)
            if future is None:
                future = loop.create_future()
                # A caller may leave before its batch fails; observe the Future
                # exception while preserving it for all surviving awaiters.
                future.add_done_callback(_observe_exception)
                self._pending[key] = future
                self._queue[key] = future
            values.append(future)
        if self._queue and (self._dispatcher is None or self._dispatcher.done()):
            self._dispatcher = asyncio.create_task(self._dispatch())
        vectors = []
        batches: dict[int, InferenceUsage] = {}
        for value in values:
            if isinstance(value, asyncio.Future):
                completed = await asyncio.shield(value)
                vectors.append(completed.vector)
                batches[completed.batch] = completed.usage
            else:
                vectors.append(value)
        usages = tuple(batches.values())
        return EmbeddingResult(
            vectors=tuple(vectors),
            usage=InferenceUsage(
                requests=sum(usage.requests for usage in usages),
                input_tokens=_sum_tokens(usages, "input_tokens"),
                output_tokens=_sum_tokens(usages, "output_tokens"),
            ),
        )

    async def _dispatch(self) -> None:
        await asyncio.sleep(self._delay)
        queued = tuple(self._queue.items())
        self._queue.clear()
        for query in (False, True):
            items = tuple((key, future) for key, future in queued if key[0] is query)
            for start in range(0, len(items), self._batch_size):
                self._batch_sequence += 1
                task = asyncio.create_task(
                    self._run_batch(items[start : start + self._batch_size], self._batch_sequence)
                )
                self._batches.add(task)
                task.add_done_callback(self._batches.discard)

    async def _run_batch(
        self,
        items: tuple[tuple[tuple[bool, str], asyncio.Future[_CompletedVector]], ...],
        batch: int,
    ) -> None:
        texts = tuple(key[1] for key, _future in items)
        try:
            if items[0][0][0] and isinstance(self._model, QueryEmbeddingModel):
                result = await self._model.embed_query(texts)
            else:
                result = await self._model.embed(texts)
            if len(result.vectors) != len(items):
                raise ValueError("embedding vector count does not match the batch")  # noqa: TRY003, TRY301
        except BaseException as error:
            for key, future in items:
                self._pending.pop(key, None)
                future.set_exception(error)
            if isinstance(error, asyncio.CancelledError):
                raise
            return
        for (key, future), vector in zip(items, result.vectors, strict=True):
            self._pending.pop(key, None)
            if self._cache_size:
                self._cache[key] = vector
                self._cache.move_to_end(key)
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            future.set_result(_CompletedVector(vector=vector, batch=batch, usage=result.usage))


def _observe_exception(future: asyncio.Future[_CompletedVector]) -> None:
    if not future.cancelled():
        future.exception()


def _sum_tokens(usages: tuple[InferenceUsage, ...], field: str) -> int | None:
    values = tuple(getattr(usage, field) for usage in usages)
    return None if not values or all(value is None for value in values) else sum(value or 0 for value in values)
