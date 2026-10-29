"""Strict service types and HTTP failure propagation."""

from types import SimpleNamespace

import httpx
import pytest

from powercontext.builtin.artifacts.memory.http_reranker import HTTPMemoryReranker


@pytest.mark.parametrize(
    "payload",
    [
        {"scores": [{"rank": True, "score": 0.5}]},
        {"scores": [{"rank": 1.0, "score": 0.5}]},
        {"scores": [{"rank": 1, "score": True}]},
        {"scores": [{"rank": 1, "score": "0.5"}]},
        {"scores": {"rank": 1, "score": 0.5}},
        {"scores": [{"rank": 1}]},
        [],
    ],
)
async def test_service_does_not_coerce_non_protocol_types(payload):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError):
            await HTTPMemoryReranker("https://scoring.invalid", client=client).rerank(
                "query", (SimpleNamespace(text="text"),), 1
            )


@pytest.mark.parametrize("status", [302, 429, 500])
async def test_non_success_http_responses_keep_httpx_error(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "unavailable"}))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as raised:
            await HTTPMemoryReranker("https://scoring.invalid", client=client).rerank(
                "query", (SimpleNamespace(text="text"),), 1
            )
    assert raised.value.response.status_code == status
