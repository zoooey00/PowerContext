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

"""Capture immutable visible Pi v3 events and resume through durable checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, JsonValue

from powercontext.sources.connectors import ConnectorRunCompletion, ConnectorRunSession, ConnectorRunStatus
from powercontext.sources.definitions import AdapterSourceDefinition, SourceDefinition
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TextEvidence


class PiSessionInput(BaseModel):
    content: bytes
    leaf_id: str | None = None


class PiEventInput(BaseModel):
    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: dict[str, JsonValue]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _event_identity(session_id: str, event_id: str) -> str:
    # A structured pair avoids ambiguous separators and bounds arbitrarily long IDs.
    digest = hashlib.sha256(_canonical([session_id, event_id]).encode()).hexdigest()
    return f"pi:{digest}"


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")  # noqa: TRY003


def _read_archive(value: PiSessionInput) -> tuple[str, dict[str, dict], str | None]:
    try:
        records = [
            json.loads(line, parse_constant=_reject_constant)
            for line in value.content.decode("utf-8-sig").splitlines()
            if line.strip()
        ]
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid UTF-8 Pi JSONL") from error  # noqa: TRY003
    if not records or not isinstance(records[0], dict):
        raise ValueError("missing Pi session header")  # noqa: TRY003
    header = records[0]
    session_id = header.get("id")
    if (
        header.get("type") != "session"
        or type(header.get("version")) is not int
        or header["version"] != 3
        or not isinstance(session_id, str)
        or not session_id.strip()
    ):
        raise ValueError("expected a Pi v3 session header with an ID")  # noqa: TRY003
    nodes: dict[str, dict] = {}
    leaf = None
    for record in records[1:]:
        identity = _validate_node(record, nodes)
        nodes[identity] = record
        leaf = identity
    if value.leaf_id is not None:
        if value.leaf_id not in nodes:
            raise ValueError("Pi leaf does not exist")  # noqa: TRY003
        leaf = value.leaf_id
    return session_id, nodes, leaf


def _validate_node(record: object, nodes: dict[str, dict]) -> str:
    if not isinstance(record, dict):
        raise ValueError("Pi nodes must be objects")  # noqa: TRY003, TRY004
    identity = record.get("id")
    if not isinstance(identity, str) or not identity.strip() or identity in nodes:
        raise ValueError("Pi node IDs must be nonempty and unique")  # noqa: TRY003
    if "parentId" not in record:
        raise ValueError("Pi node is missing parentId")  # noqa: TRY003
    parent = record["parentId"]
    if parent is not None and (not isinstance(parent, str) or parent not in nodes):
        raise ValueError("Pi parent must refer to an earlier node")  # noqa: TRY003
    if not isinstance(record.get("type"), str) or not record["type"]:
        raise ValueError("Pi node is missing its event type")  # noqa: TRY003
    return identity


def _visible_text(content: object, *, include_tool_calls: bool = True) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif include_tool_calls and block.get("type") == "toolCall":
            name, identity = block.get("name"), block.get("id")
            if not isinstance(name, str) or not isinstance(identity, str):
                raise ValueError("tool calls need a name and ID")  # noqa: TRY003
            parts.append(f"[tool_call {name} {identity}] {_canonical(block.get('arguments', {}))}")
    return "\n".join(parts)


def _event(session_id: str, record: dict) -> PiEventInput | None:
    kind = record["type"]
    role, body = "", ""
    if kind == "message":
        message = record.get("message")
        if not isinstance(message, dict):
            raise ValueError("Pi message must be an object")  # noqa: TRY003
        role = message.get("role", "")
        if not isinstance(role, str) or not role:
            raise ValueError("Pi message is missing its role")  # noqa: TRY003
        body = _visible_text(message.get("content"))
        if role == "toolResult" and body:
            body = f"[tool_result {message.get('toolName', '')} {message.get('toolCallId', '')}] {body}"
        elif role == "bashExecution":
            body = f"$ {message.get('command', '')}\n{message.get('output', '')}"
    elif kind in {"compaction", "branch_summary"}:
        role = kind
        body = record.get("summary", "")
    elif kind == "custom_message":
        role = "custom"
        body = _visible_text(record.get("content"), include_tool_calls=False)
    if not isinstance(body, str):
        raise ValueError("Pi visible body must be text")  # noqa: TRY003, TRY004
    if not body:
        return None
    return PiEventInput(
        session_id=session_id,
        event_id=record["id"],
        parent_id=record["parentId"],
        event_type=kind,
        role=role,
        content=f"{role}: {body}",
        record=record,
    )


def _branch_events(session_id: str, nodes: dict[str, dict], leaf: str | None) -> tuple[PiEventInput, ...]:
    chain = []
    while leaf is not None:
        chain.append(nodes[leaf])
        leaf = nodes[leaf]["parentId"]
    events = (_event(session_id, record) for record in reversed(chain))
    return tuple(event for event in events if event is not None)


def parse_pi_session(value: PiSessionInput) -> tuple[PiEventInput, ...]:
    """Return visible original evidence on the chosen complete ancestor chain."""
    return _branch_events(*_read_archive(value))


class PiEventSource(Source):
    event: PiEventInput


class _PiEventAdapter:
    name = "pi-event"
    input_class = PiEventInput
    source_class = PiEventSource

    async def resolve(self, value: PiEventInput, /) -> PiEventSource:
        return PiEventSource(
            name=_event_identity(value.session_id, value.event_id),
            materialization=SourceMaterialization.CAPTURED,
            event=value,
        )

    async def read(self, source: PiEventSource, /) -> PiEventInput:
        return source.event


class _PiEventProjection:
    name = "powercontext.text-evidence"
    version = "1"
    source_class = PiEventSource
    output_class = TextEvidence

    def project(self, source: PiEventSource, /) -> TextEvidence:
        return TextEvidence(
            source_type="pi-event",
            source_id=source.name,
            content=source.event.content,
            metadata=source.event.model_dump(include={"session_id", "event_id", "parent_id", "event_type", "role"}),
        )


PI_EVENT_SOURCE_DEFINITION: SourceDefinition[PiEventInput, PiEventSource, PiEventInput] = AdapterSourceDefinition(
    _PiEventAdapter(), projections=(_PiEventProjection(),)
)


class PiSessionConnector:
    """Use lifecycle-owned checkpoints for deduplication and immutable history."""

    name = "pi-session-history"
    version = "1"
    source_definitions = frozenset({"pi-event"})

    def __init__(self, path: str | Path, leaf_id: str | None = None) -> None:
        self.path = Path(path)
        self.leaf_id = leaf_id

    async def run(self, session: ConnectorRunSession, /) -> ConnectorRunCompletion:
        value = PiSessionInput(content=self.path.read_bytes(), leaf_id=self.leaf_id)
        session_id, nodes, leaf = _read_archive(value)
        events = _branch_events(session_id, nodes, leaf)
        previous = session.checkpoint or {}
        if not isinstance(previous, dict):
            raise ValueError("invalid Pi checkpoint")  # noqa: TRY003, TRY004
        imported = dict(previous.get("imported", {}))
        hashes = {
            _event_identity(session_id, event_id): hashlib.sha256(_canonical(record).encode()).hexdigest()
            for event_id, record in nodes.items()
        }
        # Check imported records on other branches too, before accepting any new event.
        for identity, digest in hashes.items():
            if identity in imported and imported[identity] != digest:
                raise ValueError("previously imported Pi event was rewritten")  # noqa: TRY003
        for event in events:
            identity = _event_identity(event.session_id, event.event_id)
            if identity not in imported:
                await session.submit(identity, "pi-event", event)
                imported[identity] = hashes[identity]
        return ConnectorRunCompletion(status=ConnectorRunStatus.COMPLETE, checkpoint={"imported": imported})
