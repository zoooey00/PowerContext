"""PowerContext HTTP adapter. No mock or local retrieval fallback."""
import asyncio
import json
import httpx
from backend.config import (
    POWERCONTEXT_SERVER_URL, POWERCONTEXT_API_TOKEN, POWERCONTEXT_SCOPE_ID,
    POWERCONTEXT_SCOPE_KEY, POWERCONTEXT_SEARCH_MODE,
)

MARKER = 'workflowlog '


class PowerContextError(RuntimeError):
    pass


class PowerContextClient:
    def __init__(self):
        self.base_url = POWERCONTEXT_SERVER_URL.rstrip('/')
        self.scope_id = POWERCONTEXT_SCOPE_ID
        self._client = None
        self._lock = asyncio.Lock()

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=15, trust_env=False,
                headers={'Authorization': f'Bearer {POWERCONTEXT_API_TOKEN}'} if POWERCONTEXT_API_TOKEN else {},
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def post(self, path, payload):
        try:
            response = await (await self._get_client()).post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise PowerContextError(f'PowerContext {path}: HTTP {error.response.status_code}') from error
        except (httpx.HTTPError, ValueError) as error:
            raise PowerContextError(f'PowerContext {path}: unavailable or invalid response') from error

    async def ensure_scope(self):
        async with self._lock:
            if not self.scope_id:
                result = await self.post('/v1/scopes', {
                    'title': 'WorkFlow AI', 'summary': 'Personal work log memory',
                    'idempotency_key': POWERCONTEXT_SCOPE_KEY,
                })
                self.scope_id = result['scope_id']
        return self.scope_id

    async def health_check(self):
        try:
            response = await (await self._get_client()).get('/health/ready')
            response.raise_for_status()
            await self.ensure_scope()
            return {'status': 'healthy', 'scope_id': self.scope_id, 'search_mode': POWERCONTEXT_SEARCH_MODE}
        except (httpx.HTTPError, PowerContextError, KeyError):
            return {'status': 'unavailable'}

    @staticmethod
    def encode_log(log):
        fields = {k: log[k] for k in ('id', 'title', 'content', 'category', 'tags', 'date')}
        return MARKER + json.dumps(fields, ensure_ascii=False, separators=(',', ':'))

    async def store_work_log(self, log):
        text = self.encode_log(log)
        if len(text.encode('utf-8')) > 8192:
            raise PowerContextError('工作日志超过 PowerContext 单条记忆 8192 UTF-8 字节限制')
        data = await self.post('/v1/memory/remember', {
            'scope_id': await self.ensure_scope(), 'kind': 'work_log', 'text': text,
        })
        records = data.get('records', [])
        if not records or not records[0].get('artifact'):
            raise PowerContextError('PowerContext did not return a memory artifact')
        return records[0]

    async def search_work_logs(self, query, limit=10):
        return await self.post('/v1/memory/search', {
            'scope_id': await self.ensure_scope(), 'query': query,
            'limit': min(limit, 50), 'mode': POWERCONTEXT_SEARCH_MODE,
        })

    async def prepare_context(self, query):
        return await self.post('/v1/context/prepare', {
            'scope_id': await self.ensure_scope(), 'query': query, 'max_bytes': 8000,
        })

    async def forget(self, record):
        return await self.post('/v1/atomic-memory/lifecycle', {
            'scope_id': await self.ensure_scope(),
            'target': {'artifact': record['artifact'], 'state_version': record['state_version']},
            'state': 'forgotten',
        })


powercontext_client = PowerContextClient()
