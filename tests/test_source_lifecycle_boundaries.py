import asyncio

import pytest
from pydantic import ValidationError

from powercontext.builtin.artifacts.memory import MemoryEntryInput, MemoryService
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import BuiltinConfig, CaptureSource, RememberMemoryRequest, open_builtin_runtime
from powercontext.builtin.runtime.source_lifecycle import SourceLifecycleEvent
from powercontext.builtin.scope import ScopeDraft


def test_failed_native_write_rolls_back_event_and_retry_completes(monkeypatch):
    async def run():
        async with open_builtin_runtime(BuiltinConfig(database=SQLiteConfig())) as runtime:
            scope = await runtime.scopes.create(
                ScopeDraft(title="Retry", summary="Atomic propagation", idempotency_key="retry")
            )
            memory = runtime.memory.for_scope(scope.scope_id)
            lifecycle = runtime.lifecycle.for_scope(scope.scope_id)
            source = await runtime.sources.for_scope(scope.scope_id).capture(
                CaptureSource(source_id="root", content="evidence", metadata={})
            )
            await lifecycle.register_source("root", source.source_ref, revision=1)
            for number in range(2):
                result = await memory.remember(
                    RememberMemoryRequest(
                        entries=(MemoryEntryInput(kind="fact", text=f"independent evidence {number}"),)
                    )
                )
                await lifecycle.register_memory(str(number), result.entry.citation, parents=("root",), policy="all")
            before = (await memory.list()).memory_ref
            original = MemoryService.forget
            calls = 0

            async def interrupt(self, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("interrupted-persistence")
                return await original(self, *args, **kwargs)

            event = SourceLifecycleEvent(node_id="root", revision=1, sequence=1, available=False, reason="withdraw")
            with monkeypatch.context() as patch:
                patch.setattr(MemoryService, "forget", interrupt)
                with pytest.raises(OSError):
                    await lifecycle.apply(event)
            assert (await memory.list()).memory_ref == before
            assert len((await memory.list()).entries) == 2
            assert await lifecycle.apply(event) == []
            after = (await memory.list(include_inactive=True)).memory_ref
            assert await lifecycle.apply(event) == []
            assert (await memory.list(include_inactive=True)).memory_ref == after
            restored = event.model_copy(update={"sequence": 2, "available": True})
            assert await lifecycle.apply(restored) == ["0", "1", "root"]

    asyncio.run(run())


@pytest.mark.parametrize("field,value", [("revision", True), ("sequence", 1.0), ("available", 1), ("reason", "  ")])
def test_event_fields_are_strict(field, value):
    values = {"node_id": "root", "revision": 1, "sequence": 1, "available": True, "reason": "restore"}
    values[field] = value
    with pytest.raises(ValidationError):
        SourceLifecycleEvent(**values)
