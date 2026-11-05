from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
import json
import os

from backend.config import APP_HOST, APP_PORT
from backend.database import (
    init_db, create_work_log, get_work_log, list_work_logs,
    update_work_log, delete_work_log, get_work_logs_by_date_range,
    get_statistics
)
from backend.models import (
    WorkLogCreate, WorkLogUpdate, WorkLogResponse,
    SearchResult, WeeklyReportRequest, WeeklyReportResponse,
    ChatRequest, ChatResponse
)
from backend.powercontext_client import powercontext_client

app = FastAPI(title="WorkFlow AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.on_event("startup")
async def startup():
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    await powercontext_client.close()


@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/api/health")
async def health_check():
    pc_health = await powercontext_client.health_check()
    return {
        "status": "ok",
        "powercontext": pc_health,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/work-logs", response_model=WorkLogResponse)
async def create_log(log: WorkLogCreate):
    date = log.date or datetime.now().strftime("%Y-%m-%d")
    log_id = await create_work_log(log.title, log.content, log.category, log.tags, date)

    pc_result = await powercontext_client.store_work_log_memory(
        log_id, log.title, log.content, log.category, log.tags, date
    )

    created = await get_work_log(log_id)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to retrieve created log")
    return created


@app.get("/api/work-logs", response_model=list[WorkLogResponse])
async def get_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    return await list_work_logs(limit, offset, category, date_from, date_to)


@app.get("/api/work-logs/{log_id}", response_model=WorkLogResponse)
async def get_log(log_id: int):
    log = await get_work_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Work log not found")
    return log


@app.put("/api/work-logs/{log_id}", response_model=WorkLogResponse)
async def update_log(log_id: int, log: WorkLogUpdate):
    existing = await get_work_log(log_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Work log not found")

    update_data = {}
    if log.title is not None:
        update_data["title"] = log.title
    if log.content is not None:
        update_data["content"] = log.content
    if log.category is not None:
        update_data["category"] = log.category
    if log.tags is not None:
        update_data["tags"] = log.tags

    if update_data:
        await update_work_log(log_id, **update_data)

        updated = await get_work_log(log_id)
        if updated:
            await powercontext_client.store_work_log_memory(
                log_id, updated["title"], updated["content"],
                updated["category"], updated["tags"], updated["date"]
            )

    result = await get_work_log(log_id)
    return result


@app.delete("/api/work-logs/{log_id}")
async def delete_log(log_id: int):
    existing = await get_work_log(log_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Work log not found")
    await delete_work_log(log_id)
    return {"message": "Work log deleted"}


@app.post("/api/search", response_model=list[SearchResult])
async def search_logs(query: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)):
    pc_result = await powercontext_client.search_work_logs(query, limit)

    if pc_result.get("success"):
        return _format_pc_search_results(pc_result["data"], query)

    all_logs = await list_work_logs(limit=200)
    query_lower = query.lower()
    results = []
    for log in all_logs:
        score = 0
        if query_lower in log["title"].lower():
            score += 10
        if query_lower in log["content"].lower():
            score += 5
        if query_lower in log["category"].lower():
            score += 3
        for tag in log.get("tags", []):
            if query_lower in tag.lower():
                score += 2
        if score > 0:
            results.append(SearchResult(
                id=log["id"], title=log["title"], content=log["content"],
                category=log["category"], tags=log["tags"], date=log["date"],
                score=float(score)
            ))
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


@app.post("/api/weekly-report", response_model=WeeklyReportResponse)
async def generate_weekly_report(req: WeeklyReportRequest):
    logs = await get_work_logs_by_date_range(req.start_date, req.end_date)
    stats = await get_statistics(req.start_date, req.end_date)

    context = await powercontext_client.build_weekly_context(logs)

    report = _generate_report_text(logs, stats, req.style)
    summary = _generate_summary(logs, stats)

    return WeeklyReportResponse(
        report=report,
        summary=summary,
        statistics=stats
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_about_work(req: ChatRequest):
    cutoff_date = (datetime.now() - timedelta(days=req.context_days)).strftime("%Y-%m-%d")
    recent_logs = await list_work_logs(limit=200, date_from=cutoff_date)

    pc_result = await powercontext_client.search_work_logs(req.question, limit=5)

    sources = []
    if pc_result.get("success"):
        sources = pc_result["data"].get("results", [])
    else:
        query_lower = req.question.lower()
        for log in recent_logs[:10]:
            if query_lower in log["title"].lower() or query_lower in log["content"].lower():
                sources.append({"id": log["id"], "title": log["title"], "date": log["date"]})

    answer = _generate_chat_answer(req.question, recent_logs, sources)

    return ChatResponse(answer=answer, sources=sources)


def _format_pc_search_results(data: dict, query: str) -> list[SearchResult]:
    results = []
    items = data.get("results", data.get("memories", []))
    for item in items:
        metadata = item.get("metadata", {})
        if metadata.get("type") == "work_log":
            results.append(SearchResult(
                id=int(metadata.get("log_id", 0)),
                title=item.get("title", item.get("content", "")[:50]),
                content=item.get("content", ""),
                category=metadata.get("category", "general"),
                tags=metadata.get("tags", []),
                date=metadata.get("date", ""),
                score=item.get("score", item.get("relevance", 0.0))
            ))
    return results


def _generate_report_text(logs: list, stats: dict, style: str) -> str:
    if not logs:
        return "## 本周工作总结\n\n本周暂无工作记录。建议及时记录每日工作内容，以便生成完整的周报。"

    lines = ["# 工作周报", ""]
    lines.append(f"**统计周期**: {logs[0]['date']} ~ {logs[-1]['date']}")
    lines.append(f"**工作天数**: {stats.get('active_days', 0)} 天")
    lines.append(f"**工作记录数**: {stats.get('total_logs', 0)} 条")
    lines.append("")

    categories = stats.get("categories", {})
    if categories:
        lines.append("## 工作分类统计")
        lines.append("")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{cat}**: {count} 条")
        lines.append("")

    lines.append("## 详细工作内容")
    lines.append("")

    current_date = None
    for log in logs:
        if log["date"] != current_date:
            current_date = log["date"]
            lines.append(f"### {current_date}")
            lines.append("")

        tags_str = f" `{'` `'.join(log['tags'])}`" if log.get('tags') else ""
        lines.append(f"#### {log['title']} [{log['category']}]{tags_str}")
        lines.append("")
        lines.append(log["content"])
        lines.append("")

    lines.append("## 下周计划")
    lines.append("")
    lines.append("（请根据本周工作进展，补充下周工作计划）")
    lines.append("")

    return "\n".join(lines)


def _generate_summary(logs: list, stats: dict) -> str:
    if not logs:
        return "本周暂无工作记录。"

    total = len(logs)
    categories = stats.get("categories", {})
    top_category = max(categories.items(), key=lambda x: x[1])[0] if categories else "general"

    unique_dates = set(log["date"] for log in logs)

    return (
        f"本周共完成 {total} 项工作记录，活跃工作 {len(unique_dates)} 天。"
        f"主要工作集中在 {top_category} 方向（{categories.get(top_category, 0)} 条）。"
        f"建议保持每日记录习惯，确保工作可追溯。"
    )


def _generate_chat_answer(question: str, logs: list, sources: list) -> str:
    if not logs:
        return "暂无相关工作记录，无法回答该问题。请先添加工作日志。"

    question_lower = question.lower()

    if "多少" in question_lower or "数量" in question_lower or "统计" in question_lower:
        total = len(logs)
        unique_dates = len(set(log["date"] for log in logs))
        categories = {}
        for log in logs:
            categories[log["category"]] = categories.get(log["category"], 0) + 1
        cat_str = "、".join(f"{k} {v} 条" for k, v in categories.items())
        return f"根据记录，您共有 {total} 条工作日志，活跃工作 {unique_dates} 天。分类统计：{cat_str}。"

    if "最近" in question_lower or "最新" in question_lower:
        recent = logs[:5]
        items = "\n".join(f"- [{log['date']}] {log['title']}" for log in recent)
        return f"最近的工作记录如下：\n{items}"

    if "总结" in question_lower or "概括" in question_lower:
        categories = {}
        for log in logs:
            categories[log["category"]] = categories.get(log["category"], 0) + 1
        summary_parts = [f"{k} 方向 {v} 项工作" for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)]
        return f"工作概况：共 {len(logs)} 条记录，主要包括{'、'.join(summary_parts)}。"

    relevant = []
    for log in logs:
        if question_lower in log["title"].lower() or question_lower in log["content"].lower():
            relevant.append(log)
        for tag in log.get("tags", []):
            if question_lower in tag.lower():
                relevant.append(log)
                break

    if relevant:
        items = "\n".join(f"- [{log['date']}] {log['title']}: {log['content'][:100]}..." for log in relevant[:5])
        return f"找到 {len(relevant)} 条相关工作记录：\n{items}"

    titles = "\n".join(f"- [{log['date']}] {log['title']}" for log in logs[:10])
    return f"未找到与\"{question}\"直接相关的记录。以下是最近的工作记录供参考：\n{titles}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
