"""Pi graph validation and lifecycle recovery beyond the sample archive."""

import json

import pytest

from powercontext.sources import ConnectorBinding, SourceDefinitionRegistry, SourceRef
from powercontext.sources.connectors import ConnectorLifecycle
from powercontext.sources.pi_session import (
    PI_EVENT_SOURCE_DEFINITION,
    PiSessionConnector,
    PiSessionInput,
    parse_pi_session,
)


def _write(path, records):
    header = {"type": "session", "version": 3, "id": "archive"}
    path.write_text("\n".join(json.dumps(row) for row in [header, *records]), encoding="utf-8")


def _message(identity, parent, text):
    return {"type": "message", "id": identity, "parentId": parent, "message": {"role": "user", "content": text}}


async def test_failed_submission_keeps_checkpoint_and_retry_preserves_events(tmp_path):
    path = tmp_path / "archive.jsonl"
    _write(path, [_message("a", None, "first"), _message("b", "a", "second")])
    registry = SourceDefinitionRegistry((PI_EVENT_SOURCE_DEFINITION,))

    class Store:
        checkpoint = None

        async def load(self, binding, /):
            return self.checkpoint

        async def save(self, binding, checkpoint, /, *, expected):
            assert expected == self.checkpoint
            self.checkpoint = checkpoint

    class Sink:
        fail = True

        def __init__(self):
            self.sources = {}

        async def submit(self, binding, item_id, definition_name, value, /):
            if value.event_id == "b" and self.fail:
                raise OSError("temporary storage failure")  # noqa: TRY003
            source = await registry.resolve(value)
            self.sources.setdefault(item_id, source)
            assert self.sources[item_id] == source
            return SourceRef(source_type=definition_name, source_id=source.name)

    store, sink = Store(), Sink()
    lifecycle = ConnectorLifecycle(sink=sink, checkpoints=store)
    binding = ConnectorBinding(
        scope_id="scope", binding_id="pi", connector_name="pi-session-history", connector_version="1"
    )
    with pytest.raises(OSError):
        await lifecycle.run(PiSessionConnector(path), binding)
    assert store.checkpoint is None
    assert len(sink.sources) == 1
    sink.fail = False
    complete = await lifecycle.run(PiSessionConnector(path), binding)
    assert complete.committed_checkpoint is not None
    assert len(sink.sources) == 2
    assert (await lifecycle.run(PiSessionConnector(path), binding)).items == ()

    # A changed record on the other branch must also fail before any new write.
    _write(path, [_message("a", None, "first"), _message("b", "a", "rewritten"), _message("c", "a", "new branch")])
    with pytest.raises(ValueError):
        await lifecycle.run(PiSessionConnector(path, "c"), binding)
    assert store.checkpoint == complete.committed_checkpoint
    assert len(sink.sources) == 2


def test_off_branch_graph_errors_and_non_json_numbers_are_rejected():
    header = '{"type":"session","version":3,"id":"archive"}\n'
    valid = json.dumps(_message("a", None, "visible"))
    for tail in [
        '{"type":"model_change","id":"b"}',
        '{"type":"model_change","id":"b","parentId":"absent"}',
        '{"type":"model_change","id":"b","parentId":null,"value":NaN}',
    ]:
        with pytest.raises(ValueError):
            parse_pi_session(PiSessionInput(content=(header + valid + "\n" + tail).encode(), leaf_id="a"))
