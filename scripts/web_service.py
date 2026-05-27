#!/usr/bin/env python3
"""
小红书行业账号ID采集工具 — Web 服务 (FastAPI)
提供REST API + 简单的管理页面

启动: uvicorn web_service:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
import time
import uuid
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="小红书行业账号ID采集工具",
    description="按行业关键词采集小红书账号ID和主页链接",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 数据模型
# ============================================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TASKS_FILE = DATA_DIR / "tasks.json"
RESULTS_DIR = DATA_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


class CreateTaskRequest(BaseModel):
    keywords: list[str]
    max_scroll: int = 20
    name: Optional[str] = None


class TaskInfo(BaseModel):
    task_id: str
    name: str
    keywords: list[str]
    status: str  # pending, running, completed, failed
    created_at: float
    completed_at: Optional[float] = None
    total_found: int = 0
    result_file: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# 任务管理
# ============================================================

def load_tasks() -> dict:
    if TASKS_FILE.exists():
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tasks(tasks: dict):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def create_task(req: CreateTaskRequest) -> TaskInfo:
    tasks = load_tasks()
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    now = time.time()

    task = {
        "task_id": task_id,
        "name": req.name or ", ".join(req.keywords[:3]) + ("..." if len(req.keywords) > 3 else ""),
        "keywords": req.keywords,
        "max_scroll": req.max_scroll,
        "status": "pending",
        "created_at": now,
        "completed_at": None,
        "total_found": 0,
        "result_file": None,
        "error": None,
    }
    tasks[task_id] = task
    save_tasks(tasks)
    return TaskInfo(**task)


def update_task(task_id: str, **kwargs):
    tasks = load_tasks()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    tasks[task_id].update(kwargs)
    save_tasks(tasks)


# ============================================================
# API 路由
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Web管理页面"""
    return HTMLResponse(INDEX_HTML)


@app.post("/api/task", response_model=TaskInfo)
async def create_collect_task(req: CreateTaskRequest):
    """创建采集任务"""
    if not req.keywords:
        raise HTTPException(status_code=400, detail="请提供至少一个关键词")

    task = create_task(req)

    # 异步执行采集（实际生产应放消息队列，这里简化）
    import asyncio
    asyncio.create_task(run_collection(task.task_id))

    return task


@app.get("/api/tasks", response_model=list[TaskInfo])
async def list_tasks():
    """获取所有任务列表"""
    tasks = load_tasks()
    return [TaskInfo(**t) for t in tasks.values()]


@app.get("/api/task/{task_id}", response_model=TaskInfo)
async def get_task(task_id: str):
    """查询单个任务状态"""
    tasks = load_tasks()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskInfo(**tasks[task_id])


@app.get("/api/task/{task_id}/result")
async def download_result(task_id: str):
    """下载采集结果"""
    tasks = load_tasks()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    if not task.get("result_file"):
        raise HTTPException(status_code=404, detail="结果文件尚未生成")

    result_path = RESULTS_DIR / task["result_file"]
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")

    return FileResponse(
        result_path,
        filename=task["result_file"],
        media_type="text/csv" if task["result_file"].endswith(".csv") else "application/json"
    )


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    tasks = load_tasks()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 清理结果文件
    task = tasks[task_id]
    if task.get("result_file"):
        result_path = RESULTS_DIR / task["result_file"]
        if result_path.exists():
            result_path.unlink()

    del tasks[task_id]
    save_tasks(tasks)
    return {"message": "删除成功"}


# ============================================================
# 后台采集执行
# ============================================================

async def run_collection(task_id: str):
    """后台执行采集任务"""
    update_task(task_id, status="running")

    tasks = load_tasks()
    task = tasks.get(task_id, {})

    try:
        # 动态导入 collector
        from collector import XiaoHongShuCollector, Config

        config = Config(
            keywords=task.get("keywords", []),
            max_scroll=task.get("max_scroll", 20),
            headless=True,
            output_format="csv",
            output_path="",
        )

        result_filename = f"result_{task_id}_{int(time.time())}.csv"
        result_path = RESULTS_DIR / result_filename
        config.output_path = str(result_path)

        async with XiaoHongShuCollector(config) as collector:
            await collector.collect()

        total = len(collector.results)
        update_task(task_id, status="completed", completed_at=time.time(),
                     total_found=total, result_file=result_filename)

    except Exception as e:
        update_task(task_id, status="failed", completed_at=time.time(), error=str(e))


# ============================================================
# 前端页面
# ============================================================

INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小红书账号ID采集工具</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        header { background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; }
        header h1 { font-size: 22px; color: #1a1a1a; }
        header p { font-size: 14px; color: #666; margin-top: 6px; }
        .card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; }
        .card h2 { font-size: 16px; margin-bottom: 16px; color: #1a1a1a; }
        .form-group { margin-bottom: 14px; }
        label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 6px; color: #444; }
        textarea, input[type="number"] { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; transition: border-color 0.2s; }
        textarea:focus, input:focus { border-color: #ff2442; }
        textarea { min-height: 80px; resize: vertical; }
        .btn { display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: #ff2442; color: #fff; }
        .btn-primary:hover { background: #e01e38; }
        .btn-primary:disabled { background: #ccc; cursor: not-allowed; }
        .btn-sm { padding: 6px 14px; font-size: 12px; }

        .task-item { padding: 14px 0; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; justify-content: space-between; }
        .task-item:last-child { border-bottom: none; }
        .task-info { flex: 1; }
        .task-name { font-weight: 500; font-size: 14px; }
        .task-meta { font-size: 12px; color: #999; margin-top: 4px; }
        .task-status { font-size: 12px; padding: 3px 10px; border-radius: 12px; }
        .status-pending { background: #fff3e0; color: #e65100; }
        .status-running { background: #e3f2fd; color: #1565c0; }
        .status-completed { background: #e8f5e9; color: #2e7d32; }
        .status-failed { background: #fce4ec; color: #c62828; }
        .task-actions { display: flex; gap: 6px; align-items: center; }

        .empty { text-align: center; color: #999; padding: 30px 0; font-size: 14px; }

        .tag { display: inline-block; background: #f0f0f0; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; }

        .toast { position: fixed; top: 20px; right: 20px; padding: 12px 20px; border-radius: 8px; color: #fff; font-size: 14px; z-index: 1000; transform: translateX(120%); transition: transform 0.3s; }
        .toast.show { transform: translateX(0); }
        .toast-success { background: #2e7d32; }
        .toast-error { background: #c62828; }

        .loading { display: inline-block; width: 14px; height: 14px; border: 2px solid #ccc; border-top-color: #ff2442; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>📕 小红书账号ID采集工具</h1>
        <p>按行业关键词采集小红书账号ID和主页链接</p>
    </header>

    <div class="card">
        <h2>📝 创建采集任务</h2>
        <div class="form-group">
            <label>关键词（每行一个，或逗号分隔）</label>
            <textarea id="keywords" placeholder="例如：&#10;健身&#10;瑜伽&#10;减脂餐&#10;健康饮食"></textarea>
        </div>
        <div class="form-group">
            <label>每个关键词最大翻页次数</label>
            <input type="number" id="maxScroll" value="20" min="1" max="100" style="width:120px">
        </div>
        <button class="btn btn-primary" id="createBtn" onclick="createTask()">🚀 开始采集</button>
    </div>

    <div class="card">
        <h2>📋 任务列表</h2>
        <div id="taskList"></div>
    </div>
</div>

<div id="toast" class="toast"></div>

<script>
    async function createTask() {
        const textarea = document.getElementById('keywords');
        const btn = document.getElementById('createBtn');
        const raw = textarea.value.trim();
        if (!raw) { showToast('请输入关键词', 'error'); return; }

        // 支持换行和逗号分隔
        const keywords = raw.split(/[,\\n]+/).map(k => k.trim()).filter(k => k);
        if (keywords.length === 0) { showToast('请输入有效关键词', 'error'); return; }

        btn.disabled = true;
        btn.innerHTML = '<span class="loading"></span> 创建中...';

        try {
            const res = await fetch('/api/task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    keywords: keywords,
                    max_scroll: parseInt(document.getElementById('maxScroll').value) || 20
                })
            });
            const data = await res.json();
            if (res.ok) {
                showToast(`任务已创建: ${data.name}`, 'success');
                textarea.value = '';
                loadTasks();
            } else {
                showToast(data.detail || '创建失败', 'error');
            }
        } catch (e) {
            showToast('网络错误: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '🚀 开始采集';
        }
    }

    async function loadTasks() {
        try {
            const res = await fetch('/api/tasks');
            const tasks = await res.json();
            renderTasks(tasks);
        } catch (e) {
            console.error('加载任务失败:', e);
        }
    }

    function renderTasks(tasks) {
        const el = document.getElementById('taskList');
        if (tasks.length === 0) {
            el.innerHTML = '<div class="empty">暂无任务，输入关键词开始采集</div>';
            return;
        }

        let html = '';
        tasks.sort((a, b) => b.created_at - a.created_at);

        for (const t of tasks) {
            const status = t.status;
            const time = new Date(t.created_at * 1000).toLocaleString();
            const keywords = t.keywords.slice(0, 5);
            const more = t.keywords.length > 5 ? `+${t.keywords.length - 5}` : '';

            html += `
                <div class="task-item">
                    <div class="task-info">
                        <div class="task-name">${t.name}</div>
                        <div class="task-meta">
                            ${keywords.map(k => `<span class="tag">${k}</span>`).join('')}
                            ${more ? `<span class="tag">${more}</span>` : ''}
                            <span style="margin-left:8px">${time}</span>
                        </div>
                    </div>
                    <div class="task-actions">
                        <span class="task-status status-${status}">${statusText(status)}</span>
                        ${t.total_found ? `<span style="font-size:12px;color:#666;">${t.total_found}条</span>` : ''}
                        ${status === 'completed' && t.result_file ? `<button class="btn btn-sm btn-primary" onclick="downloadResult('${t.task_id}')">下载</button>` : ''}
                        ${status === 'failed' ? `<span style="font-size:12px;color:#c62828;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${t.error || ''}</span>` : ''}
                    </div>
                </div>
            `;
        }
        el.innerHTML = html;

        // 如果有进行中的任务，轮询
        const hasRunning = tasks.some(t => t.status === 'running' || t.status === 'pending');
        if (hasRunning) {
            setTimeout(loadTasks, 3000);
        }
    }

    function statusText(status) {
        const map = { pending: '等待中', running: '采集中', completed: '已完成', failed: '失败' };
        return map[status] || status;
    }

    async function downloadResult(taskId) {
        window.open(`/api/task/${taskId}/result`, '_blank');
    }

    function showToast(msg, type) {
        const toast = document.getElementById('toast');
        toast.className = `toast toast-${type} show`;
        toast.textContent = msg;
        setTimeout(() => toast.classList.remove('show'), 3000);
    }

    // 初始加载
    loadTasks();
    // 每10秒刷新
    setInterval(loadTasks, 10000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
