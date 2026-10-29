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

"""Canonical UTF-8 context packs and independently verifiable prefix deltas."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass

_PACK_SCHEMA = "powercontext.context-pack.v1"
_DELTA_SCHEMA = "powercontext.context-pack-delta.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ContextPackError(ValueError):
    """The wire data or chunk boundaries violate the context-pack contract."""


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContextPackError("duplicate JSON field")  # noqa: TRY003
        result[key] = value
    return result


def _decode(wire: bytes, fields: set[str], schema: str) -> dict:
    try:
        value = json.loads(wire.decode("utf-8"), object_pairs_hook=_unique_object)
    except (AttributeError, UnicodeError, json.JSONDecodeError) as error:
        raise ContextPackError("invalid UTF-8 JSON") from error  # noqa: TRY003
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != schema:
        raise ContextPackError("invalid context-pack fields or schema")  # noqa: TRY003
    return value


def _validate_items(items: tuple[bytes, ...]) -> None:
    if not isinstance(items, tuple) or any(not isinstance(item, bytes) for item in items):
        raise ContextPackError("chunks must be a tuple of bytes")  # noqa: TRY003
    try:
        for item in items:
            item.decode("utf-8")
    except UnicodeError as error:
        raise ContextPackError("each chunk must be valid UTF-8") from error  # noqa: TRY003


def _wire_items(items: tuple[bytes, ...]) -> list[str]:
    return [base64.b64encode(item).decode("ascii") for item in items]


def _read_items(value: object) -> tuple[bytes, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContextPackError("wire chunks must be a Base64 string array")  # noqa: TRY003
    try:
        items = tuple(base64.b64decode(item, validate=True) for item in value)
    except (ValueError, binascii.Error) as error:
        raise ContextPackError("invalid Base64") from error  # noqa: TRY003
    if _wire_items(items) != value:
        raise ContextPackError("noncanonical Base64")  # noqa: TRY003
    _validate_items(items)
    return items


def _validate_digest(value: object) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ContextPackError("invalid SHA-256 digest")  # noqa: TRY003


@dataclass(frozen=True, slots=True)
class ContextPack:
    """An immutable full pack whose digest covers the exact chunk sequence."""

    items: tuple[bytes, ...]

    def __post_init__(self) -> None:
        _validate_items(self.items)

    @classmethod
    def build(cls, items: tuple[bytes, ...]) -> ContextPack:
        return cls(items)

    @classmethod
    def from_content(cls, content: str | None, *, chunk_bytes: int = 512) -> ContextPack:
        if type(chunk_bytes) is not int or chunk_bytes <= 0:
            raise ContextPackError("chunk_bytes must be a positive integer")  # noqa: TRY003
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise ContextPackError("content must be UTF-8 text")  # noqa: TRY003
        try:
            raw = content.encode("utf-8")
        except UnicodeError as error:
            raise ContextPackError("content must be valid UTF-8") from error  # noqa: TRY003
        items = []
        start = 0
        while start < len(raw):
            end = min(start + chunk_bytes, len(raw))
            # Only continuation bytes can require moving the boundary back.
            while end < len(raw) and raw[end] & 0xC0 == 0x80:
                end -= 1
            if end == start:
                raise ContextPackError("chunk limit cannot contain a UTF-8 character")  # noqa: TRY003
            items.append(raw[start:end])
            start = end
        return cls.build(tuple(items))

    @property
    def digest(self) -> str:
        unsigned = {"schema": _PACK_SCHEMA, "items": _wire_items(self.items)}
        return "sha256:" + hashlib.sha256(_encode(unsigned)).hexdigest()

    @property
    def byte_count(self) -> int:
        return len(self.to_bytes())

    def to_bytes(self) -> bytes:
        payload = {"schema": _PACK_SCHEMA, "items": _wire_items(self.items), "digest": self.digest, "byte_count": 0}
        while True:
            wire = _encode(payload)
            if len(wire) == payload["byte_count"]:
                return wire
            payload["byte_count"] = len(wire)

    @classmethod
    def from_bytes(cls, wire: bytes) -> ContextPack:
        value = _decode(wire, {"schema", "items", "digest", "byte_count"}, _PACK_SCHEMA)
        pack = cls.build(_read_items(value["items"]))
        if value["digest"] != pack.digest:
            raise ContextPackError("pack digest mismatch")  # noqa: TRY003
        if type(value["byte_count"]) is not int or value["byte_count"] != pack.byte_count:
            raise ContextPackError("pack byte count mismatch")  # noqa: TRY003
        return pack


@dataclass(frozen=True, slots=True)
class ContextPackDelta:
    """Keep a prefix of the verified base, then append exact target chunks."""

    base_digest: str
    target_digest: str
    prefix_items: int
    appended: tuple[bytes, ...]

    def __post_init__(self) -> None:
        _validate_digest(self.base_digest)
        _validate_digest(self.target_digest)
        if type(self.prefix_items) is not int or self.prefix_items < 0:
            raise ContextPackError("prefix_items must be a nonnegative integer")  # noqa: TRY003
        _validate_items(self.appended)

    @classmethod
    def between(cls, base: ContextPack, target: ContextPack) -> ContextPackDelta:
        prefix = 0
        for left, right in zip(base.items, target.items, strict=False):
            if left != right:
                break
            prefix += 1
        return cls(base.digest, target.digest, prefix, target.items[prefix:])

    @property
    def byte_count(self) -> int:
        return len(self.to_bytes())

    def to_bytes(self) -> bytes:
        return _encode({
            "schema": _DELTA_SCHEMA,
            "base_digest": self.base_digest,
            "target_digest": self.target_digest,
            "prefix_items": self.prefix_items,
            "appended": _wire_items(self.appended),
        })

    @classmethod
    def from_bytes(cls, wire: bytes) -> ContextPackDelta:
        value = _decode(wire, {"schema", "base_digest", "target_digest", "prefix_items", "appended"}, _DELTA_SCHEMA)
        return cls(value["base_digest"], value["target_digest"], value["prefix_items"], _read_items(value["appended"]))


def apply_context_pack_delta(base: ContextPack, delta: ContextPackDelta) -> ContextPack:
    """Validate both references and reconstruct without any sender-owned state."""
    if base.digest != delta.base_digest:
        raise ContextPackError("delta base digest mismatch")  # noqa: TRY003
    if delta.prefix_items > len(base.items):
        raise ContextPackError("delta prefix exceeds the base")  # noqa: TRY003
    target = ContextPack.build(base.items[: delta.prefix_items] + delta.appended)
    if target.digest != delta.target_digest:
        raise ContextPackError("delta target digest mismatch")  # noqa: TRY003
    return target
