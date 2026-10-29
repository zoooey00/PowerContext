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

"""Persistent source support graphs and atomic native availability propagation."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator
from sqlalchemy import insert, select, update

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import MemoryCitation
from powercontext.builtin.persistence.artifact_governance import ArtifactLifecycleState
from powercontext.builtin.persistence.tables import SOURCE_LIFECYCLE_TABLE
from powercontext.builtin.sources import validate_scope_id
from powercontext.sources import SourceRef


class SourceLifecycleError(ValueError):
    """Invalid lifecycle registration, event or resolution."""


class SourceLifecycleEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    revision: StrictInt = Field(gt=0)
    sequence: StrictInt = Field(gt=0)
    available: StrictBool
    reason: str

    @field_validator("node_id", "reason")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must-not-be-blank")
        return value


class SourceLifecycle:
    def __init__(self, contexts):
        self._contexts = contexts

    def for_scope(self, scope_id: str):
        return ScopedSourceLifecycle(self._contexts, validate_scope_id(scope_id))


class ScopedSourceLifecycle:
    def __init__(self, contexts, scope_id):
        self._contexts = contexts
        self.scope_id = scope_id

    async def _load(self, connection):
        payload = await connection.scalar(
            select(SOURCE_LIFECYCLE_TABLE.c.graph).where(SOURCE_LIFECYCLE_TABLE.c.scope_id == self.scope_id)
        )
        return {} if payload is None else json.loads(payload)

    async def _save(self, connection, graph):
        table = SOURCE_LIFECYCLE_TABLE
        exists = await connection.scalar(select(table.c.scope_id).where(table.c.scope_id == self.scope_id))
        payload = json.dumps(graph, ensure_ascii=False)
        if exists is None:
            await connection.execute(insert(table).values(scope_id=self.scope_id, graph=payload))
        else:
            await connection.execute(update(table).where(table.c.scope_id == self.scope_id).values(graph=payload))

    async def register_source(self, node_id, source_ref, *, revision):
        if type(revision) is not int or revision <= 0 or not isinstance(source_ref, SourceRef):
            raise SourceLifecycleError("invalid-source-registration")
        await self._register(node_id, "source", source_ref, (), "all", revision)

    async def register_memory(self, node_id, citation, *, parents, policy):
        if not isinstance(citation, MemoryCitation):
            raise SourceLifecycleError("invalid-Memory-citation")
        await self._register(node_id, "memory", citation, parents, policy, None)

    async def register_topic(self, node_id, artifact_ref, *, parents, policy):
        if not isinstance(artifact_ref, ArtifactRef) or artifact_ref.family != "topic-memory":
            raise SourceLifecycleError("invalid-Topic-reference")
        await self._register(node_id, "topic", artifact_ref, parents, policy, None)

    async def _register(self, node_id, kind, reference, parents, policy, revision):
        if not isinstance(node_id, str) or not node_id.strip():
            raise SourceLifecycleError("invalid-node-identifier")
        parents = tuple(parents)
        if policy not in ("all", "any") or (kind != "source" and not parents):
            raise SourceLifecycleError("invalid-dependency-policy")
        if any(not isinstance(parent, str) for parent in parents) or len(set(parents)) != len(parents):
            raise SourceLifecycleError("invalid-duplicate-parents")
        binding = {
            "kind": kind,
            "reference": reference.model_dump(mode="json"),
            "parents": list(parents),
            "policy": policy,
            "revision": revision,
        }
        async with self._contexts.database.transaction() as connection:
            graph = await self._load(connection)
            if node_id in graph:
                if any(graph[node_id][key] != value for key, value in binding.items()):
                    raise SourceLifecycleError("node-already-has-a-different-binding")
                return
            if node_id in parents or any(parent not in graph for parent in parents):
                raise SourceLifecycleError("parents-must-already-be-registered")
            services = self._contexts._services_for(self.scope_id)
            try:
                if kind == "source":
                    await services.repositories.sources.get(connection, self.scope_id, reference)
                elif kind == "memory":
                    _, catalog = services.sources(connection)
                    await services.memory(catalog, connection).validate_citation(reference)
                else:
                    await services.repositories.artifacts.get(connection, self.scope_id, reference)
            except Exception as error:
                raise SourceLifecycleError("reference-is-not-readable-in-this-scope") from error
            graph[node_id] = dict(binding, available=True, event=None)
            await self._propagate(connection, graph, "dependency registration")
            await self._save(connection, graph)

    async def apply(self, event: SourceLifecycleEvent):
        if not isinstance(event, SourceLifecycleEvent):
            raise SourceLifecycleError("invalid-event")
        async with self._contexts.database.transaction() as connection:
            graph = await self._load(connection)
            node = graph.get(event.node_id)
            if node is None or node["kind"] != "source" or node["revision"] != event.revision:
                raise SourceLifecycleError("unknown-source-or-lifecycle-revision")
            payload = event.model_dump(mode="json")
            previous = node["event"]
            if previous is not None and event.sequence <= previous["sequence"]:
                if payload != previous:
                    raise SourceLifecycleError("event-sequence-conflict")
                return sorted(key for key, value in graph.items() if value["available"])
            node["event"] = payload
            node["available"] = event.available
            await self._propagate(connection, graph, event.reason)
            await self._save(connection, graph)
            return sorted(key for key, value in graph.items() if value["available"])

    async def _propagate(self, connection, graph, reason):
        services = self._contexts._services_for(self.scope_id)
        _, catalog = services.sources(connection)
        memory = services.memory(catalog, connection)
        # Registration order is a topological order: every parent must preexist.
        for node in graph.values():
            kind = node["kind"]
            if kind == "source":
                continue
            support = [graph[parent]["available"] for parent in node["parents"]]
            available = all(support) if node["policy"] == "all" else any(support)
            if kind == "memory":
                citation = MemoryCitation.model_validate(node["reference"])
                entry = await memory.validate_citation(citation)
                head = await memory.head(citation.memory_ref.artifact_id)
                transition = memory.reactivate if available else memory.forget
                await transition(head, entries=(entry,), reason=reason)
            else:
                ref = ArtifactRef.model_validate(node["reference"])
                governance = services.repositories.governance
                current = await governance.get(connection, self.scope_id, ref.family, ref.artifact_id)
                target = ArtifactLifecycleState.ACTIVE if available else ArtifactLifecycleState.DEPRECATED
                if current.lifecycle_state != target:
                    await governance.transition(
                        connection,
                        self.scope_id,
                        ref.family,
                        ref.artifact_id,
                        current.governance_generation,
                        target,
                        None,
                    )
            node["available"] = available

    async def resolve(self, node_id, *, purpose):
        if purpose not in ("generation", "audit"):
            raise SourceLifecycleError("unknown-resolution-purpose")
        async with self._contexts.database.transaction() as connection:
            node = (await self._load(connection)).get(node_id)
            if node is None or (purpose == "generation" and not node["available"]):
                raise SourceLifecycleError("node-unavailable-for-this-purpose")
            model = {"source": SourceRef, "memory": MemoryCitation, "topic": ArtifactRef}[node["kind"]]
            return model.model_validate(node["reference"])
