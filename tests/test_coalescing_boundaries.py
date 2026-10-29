"""Late waiters, independent failures, and asymmetric query embeddings."""

import asyncio

import pytest

from powercontext.builtin.artifacts.memory import EmbeddingProfile
from powercontext.builtin.inference import EmbeddingResult, InferenceUsage
from powercontext.builtin.inference.coalescing import CoalescingEmbeddingModel


class _Model:
    profile = EmbeddingProfile(profile_id="regression", model="local", dimension=1)


async def test_late_waiter_shares_uncached_work_after_first_caller_cancels():
    class Blocked(_Model):
        def __init__(self):
            self.calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def embed(self, texts):
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return EmbeddingResult(vectors=((2.0,),), usage=InferenceUsage(requests=3, input_tokens=7, output_tokens=2))

    base = Blocked()
    wrapper = CoalescingEmbeddingModel(base, coalesce_ms=0, cache_size=0)
    first = asyncio.create_task(wrapper.embed(("shared",)))
    await base.started.wait()
    second = asyncio.create_task(wrapper.embed(("shared", "shared")))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    base.release.set()
    result = await second
    assert result.vectors == ((2.0,), (2.0,))
    assert result.usage == InferenceUsage(requests=3, input_tokens=7, output_tokens=2)
    assert base.calls == 1
    await wrapper.embed(("shared",))
    assert base.calls == 2


async def test_failed_batch_does_not_prevent_independent_success_or_retry():
    class Flaky(_Model):
        fail = True

        async def embed(self, texts):
            if texts == ("bad",) and self.fail:
                raise RuntimeError("controlled failure")  # noqa: TRY003
            return EmbeddingResult(vectors=tuple((float(len(text)),) for text in texts))

    base = Flaky()
    wrapper = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=0)
    failed, succeeded = await asyncio.gather(wrapper.embed(("bad",)), wrapper.embed(("good",)), return_exceptions=True)
    assert isinstance(failed, RuntimeError)
    assert succeeded.vectors == ((4.0,),)
    base.fail = False
    assert (await wrapper.embed(("bad",))).vectors == ((3.0,),)
    assert (await wrapper.embed(("good",))).usage.requests == 0


async def test_asymmetric_query_cache_stays_separate_from_document_vectors():
    class Asymmetric(_Model):
        async def embed(self, texts):
            return EmbeddingResult(vectors=tuple((1.0,) for _ in texts), usage=InferenceUsage(requests=1))

        async def embed_query(self, texts):
            return EmbeddingResult(vectors=tuple((9.0,) for _ in texts), usage=InferenceUsage(requests=2))

    wrapper = CoalescingEmbeddingModel(Asymmetric(), coalesce_ms=0)
    document, query = await asyncio.gather(wrapper.embed(("text",)), wrapper.embed_query(("text",)))
    assert document.vectors == ((1.0,),) and document.usage.requests == 1
    assert query.vectors == ((9.0,),) and query.usage.requests == 2
    assert (await wrapper.embed_query(("text",))).usage.requests == 0
