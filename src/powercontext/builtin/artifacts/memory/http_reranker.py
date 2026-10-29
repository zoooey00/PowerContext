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

"""Identity-preserving HTTP scoring with bounded batches and global ranking."""

from __future__ import annotations

import math

import httpx

from powercontext.builtin.artifacts.memory.models import MemoryHit
from powercontext.builtin.artifacts.memory.reranking import MemoryRerankDecision
from powercontext.builtin.inference import InferenceUsage


class HTTPMemoryReranker:
    """Score every original candidate once and choose a stable global top-k."""

    def __init__(
        self,
        endpoint: str,
        *,
        client: httpx.AsyncClient,
        batch_size: int = 32,
        policy_id: str = "http-cross-encoder-v1",
    ) -> None:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")  # noqa: TRY003
        self.endpoint = endpoint
        self.client = client
        self.batch_size = batch_size
        self.policy_id = policy_id

    async def rerank(self, query: str, candidates: tuple[MemoryHit, ...], limit: int, /) -> MemoryRerankDecision:
        if not candidates or type(limit) is not int or not 1 <= limit <= len(candidates):
            raise ValueError("limit must select at least one and at most all candidates")  # noqa: TRY003
        scores: dict[int, float] = {}
        requests = 0
        for start in range(0, len(candidates), self.batch_size):
            batch = [
                {"rank": index + 1, "text": candidates[index].text}
                for index in range(start, min(start + self.batch_size, len(candidates)))
            ]
            response = await self.client.post(self.endpoint, json={"query": query, "candidates": batch})
            requests += 1
            response.raise_for_status()
            payload = response.json()
            scores.update(_validate_scores(payload, {item["rank"] for item in batch}))
        ranks = sorted(scores, key=lambda rank: (-scores[rank], rank))
        return MemoryRerankDecision(selected_ranks=tuple(ranks[:limit]), usage=InferenceUsage(requests=requests))


def _validate_scores(payload: object, expected: set[int]) -> dict[int, float]:
    if not isinstance(payload, dict) or set(payload) != {"scores"} or not isinstance(payload["scores"], list):
        raise ValueError("response must contain only a scores array")  # noqa: TRY003
    scores: dict[int, float] = {}
    for item in payload["scores"]:
        if not isinstance(item, dict) or set(item) != {"rank", "score"}:
            raise ValueError("each score must contain exactly rank and score")  # noqa: TRY003
        rank, score = item["rank"], item["score"]
        if type(rank) is not int or rank not in expected or rank in scores:
            raise ValueError("response ranks must cover exactly this batch once")  # noqa: TRY003
        if type(score) not in {int, float}:
            raise ValueError("score must be a finite number")  # noqa: TRY003
        try:
            finite = math.isfinite(score)
        except OverflowError as error:
            raise ValueError("score must be a finite number") from error  # noqa: TRY003
        if not finite:
            raise ValueError("score must be a finite number")  # noqa: TRY003
        scores[rank] = float(score)
    if scores.keys() != expected:
        raise ValueError("response is missing ranks")  # noqa: TRY003
    return scores
