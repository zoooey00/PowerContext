"""Single-user local application; PowerContext is required for memory features."""
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from backend.config import APP_HOST, APP_PORT
from backend import database as db
from backend.models import (
    WorkLogCreate, WorkLogUpdate, WorkLogResponse, SearchResult,
    WeeklyReportRequest, WeeklyReportResponse, ChatRequest, ChatResponse,
)
from backend.powercontext_client import powercontext_client as pc, PowerContextError, MARKER

mutation_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app):
    await db.init_db()
    yield
    await pc.close()


app = FastAPI(title="WorkFlow AI", version="1.1.0", lifespan=lifespan)
frontend_dir = Path(__file__).resolve().parents[1] / 'frontend'
app.mount('/static', StaticFiles(directory=frontend_dir), name='static')


@app.exception_handler(PowerContextError)
async def memory_error(request, error):
    return JSONResponse(status_code=502, content={'detail': str(error), 'memory_backend': 'unavailable'})


@app.get('/')
async def root():
    return FileResponse(frontend_dir / 'index.html')


@app.get('/api/health')
async def health():
    state = await pc.health_check()
    return {'status': 'ok' if state['status'] == 'healthy' else 'degraded',
            'powercontext': state, 'timestamp': datetime.now().isoformat()}


async def with_ref(log):
    record = await db.get_memory_ref(log['id'])
    return {**log, 'memory_ref': record['artifact'] if record else None}


@app.post('/api/work-logs', response_model=WorkLogResponse)
async def create_log(log: WorkLogCreate):
    async with mutation_lock:
        log_id = await db.create_work_log(log.title, log.content, log.category, log.tags, log.date.isoformat())
        created = await db.get_work_log(log_id)
        try:
            record = await pc.store_work_log(created)
            await db.save_memory_ref(log_id, record)
        except PowerContextError:
            await db.delete_work_log(log_id)
            raise
        return await with_ref(created)


@app.get('/api/work-logs', response_model=list[WorkLogResponse])
async def get_logs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                   category: str | None = None, date_from: str | None = None, date_to: str | None = None):
    logs = await db.list_work_logs(limit, offset, category, date_from, date_to)
    return [await with_ref(log) for log in logs]


@app.get('/api/work-logs/{log_id}', response_model=WorkLogResponse)
async def get_log(log_id: int):
    log = await db.get_work_log(log_id)
    if not log:
        raise HTTPException(404, 'Work log not found')
    return await with_ref(log)


@app.post('/api/work-logs/{log_id}/sync', response_model=WorkLogResponse)
async def sync_log(log_id: int):
    async with mutation_lock:
        log = await db.get_work_log(log_id)
        if not log:
            raise HTTPException(404, 'Work log not found')
        if await db.get_memory_ref(log_id) is None:
            await db.save_memory_ref(log_id, await pc.store_work_log(log))
        return await with_ref(log)


@app.put('/api/work-logs/{log_id}', response_model=WorkLogResponse)
async def update_log(log_id: int, update: WorkLogUpdate):
    async with mutation_lock:
        old = await db.get_work_log(log_id)
        if not old:
            raise HTTPException(404, 'Work log not found')
        changes = update.model_dump(exclude_none=True)
        if not changes:
            return await with_ref(old)
        current = {**old, **changes}
        previous = await db.get_memory_ref(log_id)
        record = await pc.store_work_log(current)
        if previous:
            try:
                await pc.forget(previous)
            except PowerContextError:
                await pc.forget(record)
                raise
        await db.update_work_log(log_id, **changes)
        await db.save_memory_ref(log_id, record)
        return await with_ref(await db.get_work_log(log_id))


@app.delete('/api/work-logs/{log_id}')
async def delete_log(log_id: int):
    async with mutation_lock:
        if not await db.get_work_log(log_id):
            raise HTTPException(404, 'Work log not found')
        record = await db.get_memory_ref(log_id)
        if record:
            await pc.forget(record)
        await db.delete_work_log(log_id)
        await db.remove_memory_ref(log_id)
        return {'message': '日志已删除，对应记忆已移出主动召回'}


async def recalled_logs(query, limit=50):
    data = await pc.search_work_logs(query, limit)
    results = []
    seen = set()
    for hit in data.get('hits', []):
        memory = hit.get('memory', {})
        text = memory.get('text', '')
        if not text.startswith(MARKER):
            continue
        try:
            stored = json.loads(text[len(MARKER):])
            log_id = int(stored['id'])
        except (ValueError, TypeError, KeyError):
            continue
        local = await db.get_work_log(log_id)
        record = await db.get_memory_ref(log_id)
        # Filter foreign/deleted/obsolete memories even after an interrupted update.
        if not local or not record or record['artifact'] != memory.get('artifact') or log_id in seen:
            continue
        if pc.encode_log(local) != text:
            continue
        seen.add(log_id)
        # The displayed fields come from the actual recalled memory.
        results.append({**local, **stored, 'memory_ref': memory['artifact'],
                        'score': hit['score'], 'matched_by': hit.get('matched_by', [])})
    return results


@app.get('/api/search', response_model=list[SearchResult])
@app.post('/api/search', response_model=list[SearchResult])
async def search(query: str = Query(..., min_length=1, max_length=1000),
                 limit: int = Query(10, ge=1, le=50)):
    return (await recalled_logs(query, 50))[:limit]


@app.post('/api/weekly-report', response_model=WeeklyReportResponse)
async def weekly_report(req: WeeklyReportRequest):
    start, end = req.start_date.isoformat(), req.end_date.isoformat()
    expected = await db.get_work_logs_by_date_range(start, end)
    recalled = await recalled_logs('workflowlog', 50)
    logs = sorted([log for log in recalled if start <= log['date'] <= end], key=lambda log: (log['date'], log['id']))
    if {log['id'] for log in logs} != {log['id'] for log in expected}:
        raise HTTPException(409, '部分日志未同步或超出 50 条召回窗口。请先同步日志或使用独立 Scope，缩小数据规模后重试。')
    context = await pc.prepare_context('workflowlog')
    stats = {'total_logs': len(logs), 'active_days': len({log['date'] for log in logs}), 'categories': {}}
    for log in logs:
        stats['categories'][log['category']] = stats['categories'].get(log['category'], 0) + 1
    lines = [f'# 工作周报', f'**统计周期**: {start} ~ {end}', f'**工作天数**: {stats["active_days"]} 天', '']
    for log in logs:
        lines.append(f'## [{log["date"]}] {log["title"]}')
        lines.append(log['content'] if req.style != 'concise' else log['content'][:100])
        if req.style == 'detailed':
            lines.append(f'分类：{log["category"]}；标签：{", ".join(log["tags"])}')
        ref = log['memory_ref']
        lines.append(f'记忆依据：{ref["family"]}/{ref["artifact_id"]}@{ref["revision"]}')
        lines.append('')
    if not logs:
        lines.append('所选周期暂无工作记录。')
    summary = f'从 PowerContext 实际召回 {len(logs)} 条日志，覆盖 {stats["active_days"]} 天。'
    return WeeklyReportResponse(
        report='\n'.join(lines), summary=summary, statistics=stats,
        memory_evidence=[{'id': log['id'], 'title': log['title'], 'date': log['date'], 'memory_ref': log['memory_ref']} for log in logs],
        memory_context=context,
    )


@app.post('/api/chat', response_model=ChatResponse)
async def chat(req: ChatRequest):
    cutoff = (date.today() - timedelta(days=req.context_days - 1)).isoformat()
    today = date.today().isoformat()
    broad = any(word in req.question for word in ('多少', '数量', '统计', '总结', '最近', '最新'))
    query = 'workflowlog' if broad else req.question
    logs = [log for log in await recalled_logs(query, 50) if cutoff <= log['date'] <= today]
    if '这周' in req.question or '本周' in req.question:
        monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        logs = [log for log in logs if log['date'] >= monday]
    if broad:
        expected = await db.get_work_logs_by_date_range(
            max(cutoff, monday) if ('这周' in req.question or '本周' in req.question) else cutoff, today)
        if {log['id'] for log in logs} != {log['id'] for log in expected}:
            raise HTTPException(409, '召回窗口不完整，请先同步日志或使用独立 Scope；未将部分结果当作完整统计。')
    if not logs:
        answer = 'PowerContext 在指定时间范围内未召回相关日志。全文模式建议搜索 JWT 等原文关键词。'
    else:
        logs.sort(key=lambda log: (log['date'], log['id']), reverse=True)
        answer = f'根据 PowerContext 召回的记忆，共 {len(logs)} 条相关工作日志：\n'
        answer += '\n'.join(f'- [{log["date"]}] {log["title"]}：{log["content"]}' for log in logs[:10])
    return ChatResponse(answer=answer, sources=[
        {'id': log['id'], 'title': log['title'], 'date': log['date'], 'memory_ref': log['memory_ref']} for log in logs
    ])


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
