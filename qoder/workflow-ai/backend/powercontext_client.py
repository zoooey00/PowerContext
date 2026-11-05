import httpx
from backend.config import POWERCONTEXT_SERVER_URL, POWERCONTEXT_API_TOKEN, POWERCONTEXT_SCOPE_ID
import json
from datetime import datetime


class PowerContextClient:
    def __init__(self):
        self.base_url = POWERCONTEXT_SERVER_URL.rstrip("/")
        self.token = POWERCONTEXT_API_TOKEN
        self.scope_id = POWERCONTEXT_SCOPE_ID
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.token}"} if self.token else {}
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> dict:
        client = await self._get_client()
        try:
            resp = await client.get("/health/ready")
            return {"status": "healthy" if resp.status_code == 200 else "unhealthy", "status_code": resp.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def remember(self, content: str, metadata: dict = None) -> dict:
        client = await self._get_client()
        payload = {
            "scope_id": self.scope_id,
            "content": content,
        }
        if metadata:
            payload["metadata"] = metadata
        try:
            resp = await client.post("/v1/memory/remember", json=payload)
            if resp.status_code in (200, 201):
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_memory(self, query: str, limit: int = 10) -> dict:
        client = await self._get_client()
        payload = {
            "scope_id": self.scope_id,
            "query": query,
            "limit": limit,
        }
        try:
            resp = await client.post("/v1/memory/search", json=payload)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def prepare_context(self, query: str, sections: list = None) -> dict:
        client = await self._get_client()
        payload = {
            "scope_id": self.scope_id,
            "query": query,
        }
        if sections:
            payload["sections"] = sections
        try:
            resp = await client.post("/v1/context/prepare", json=payload)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def store_work_log_memory(self, log_id: int, title: str, content: str, category: str, tags: list, date: str):
        memory_content = f"""工作日志 #{log_id}
标题: {title}
日期: {date}
分类: {category}
标签: {', '.join(tags) if tags else '无'}
内容: {content}"""
        metadata = {
            "type": "work_log",
            "log_id": str(log_id),
            "category": category,
            "date": date,
            "tags": tags,
        }
        return await self.remember(memory_content, metadata)

    async def search_work_logs(self, query: str, limit: int = 10):
        return await self.search_memory(query, limit)

    async def build_weekly_context(self, logs: list[dict]) -> str:
        if not logs:
            return "本周暂无工作记录。"

        context_parts = [f"以下是 {logs[0]['date']} 至 {logs[-1]['date']} 的工作记录汇总：\n"]
        for log in logs:
            tags_str = f" [{', '.join(log['tags'])}]" if log.get('tags') else ""
            context_parts.append(
                f"- [{log['date']}] [{log['category']}] {log['title']}{tags_str}\n  {log['content'][:200]}"
            )
        return "\n".join(context_parts)


powercontext_client = PowerContextClient()
