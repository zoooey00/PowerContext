"""Malformed wire values, UTF-8 boundaries, and empty runtime results."""

import json
import random

import pytest

from powercontext.builtin.runtime import BuiltinConfig, PrepareContextRequest, open_builtin_runtime
from powercontext.builtin.runtime.context_pack import (
    ContextPack,
    ContextPackDelta,
    ContextPackError,
    apply_context_pack_delta,
)
from powercontext.builtin.scope import ScopeDraft


def test_utf8_chunking_preserves_random_multilingual_content():
    randomizer = random.Random(2491)  # noqa: S311 - Reproducible test inputs, not cryptographic material.
    for limit in (1, 2, 3, 4, 7, 16, 512):
        for _ in range(12):
            text = "".join(randomizer.choice('a\n\r"中海é🙂') for _ in range(90))
            if any(len(character.encode()) > limit for character in text):
                with pytest.raises(ContextPackError):
                    ContextPack.from_content(text, chunk_bytes=limit)
                continue
            pack = ContextPack.from_content(text, chunk_bytes=limit)
            assert b"".join(pack.items).decode() == text
            assert all(len(item) <= limit and item.decode() for item in pack.items)
            assert ContextPack.from_bytes(pack.to_bytes()) == pack


@pytest.mark.parametrize("changes", [{"extra": 1}, {"byte_count": True}, {"items": ["YQ==\n"]}, {"items": ["/w=="]}])
def test_pack_rejects_malformed_wire(changes):
    payload = json.loads(ContextPack.build((b"a",)).to_bytes())
    with pytest.raises(ContextPackError):
        ContextPack.from_bytes(json.dumps({**payload, **changes}).encode())


def test_duplicate_wire_fields_are_rejected():
    wire = ContextPack.build(()).to_bytes()
    with pytest.raises(ContextPackError):
        ContextPack.from_bytes(wire[:-1] + b',"items":[]}')


async def test_empty_prepare_and_delta_rebuild_empty_bytes():
    async with open_builtin_runtime(BuiltinConfig()) as runtime:
        scope = await runtime.scopes.create(ScopeDraft(title="Empty", summary="Empty context", idempotency_key="empty"))
        application = runtime.context.for_scope(scope.scope_id)
        request = PrepareContextRequest(query="no matching memories", max_bytes=4096)
        ordinary = await application.prepare(request)
        assert ordinary.content is None
        pack = await application.prepare_incremental(request)
        assert pack.items == ()
        base = ContextPack.from_content("previous content")
        delta = await application.prepare_incremental(request, base_pack=base)
        assert isinstance(delta, ContextPackDelta)
        assert apply_context_pack_delta(base, ContextPackDelta.from_bytes(delta.to_bytes())).items == ()
