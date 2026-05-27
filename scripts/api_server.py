#!/usr/bin/env python3
"""
小红书行业账号ID采集工具 — 独立API服务
供外部系统通过HTTP接口调用采集任务

启动: python api_server.py --port 8000
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# ============================================================
# 确保能找到 collector 模块
# ============================================================
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================
# 数据存储
# ============================================================
DATA_DIR = SCRIPT_DIR / "api_data"
TASKS_FILE = DATA_DIR / "tasks.json"
RESULTS_DIR = DATA_DIR / "results"
DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


def load_tasks() -> dict:
    if TASKS_FILE.exists():
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tasks(tasks: dict):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ============================================================
# API Handler 实现（纯函数，无框架依赖）
# ============================================================

def parse_request(method: str, path: str, body: Optional[bytes] = None) -> dict:
    """简单的HTTP请求路由"""
    # POST /api/task — 创建任务
    if method == "POST" and path == "/api/task":
        if not body:
            return {"status": 400, "body": {"error": "请求体为空"}}
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return {"status": 400, "body": {"error": "无效的JSON"}}

        keywords = data.get("keywords", [])
        if not keywords or not isinstance(keywords, list):
            return {"status": 400, "body": {"error": "请提供关键词列表"}}

        max_scroll = data.get("max_scroll", 20)
        output_format = data.get("format", "csv")

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = {
            "task_id": task_id,
            "keywords": keywords,
            "max_scroll": max_scroll,
            "format": output_format,
            "status": "pending",
            "created_at": time.time(),
            "completed_at": None,
            "total_found": 0,
            "result_file": None,
            "error": None,
        }

        tasks = load_tasks()
        tasks[task_id] = task
        save_tasks(tasks)

        # 异步执行（单元测试中可能无事件循环）
        try:
            asyncio.create_task(run_task(task_id))
        except RuntimeError:
            pass

        return {"status": 200, "body": {"task_id": task_id, "status": "pending", "keywords": keywords}}

    # GET /api/task/{task_id} — 查询任务
    if method == "GET" and path.startswith("/api/task/"):
        task_id = path.split("/api/task/")[1].split("/")[0]
        tasks = load_tasks()
        if task_id not in tasks:
            return {"status": 404, "body": {"error": "任务不存在"}}
        return {"status": 200, "body": tasks[task_id]}

    # GET /api/task/{task_id}/result — 下载结果
    if method == "GET" and "/result" in path:
        task_id = path.split("/api/task/")[1].split("/")[0]
        tasks = load_tasks()
        if task_id not in tasks:
            return {"status": 404, "body": {"error": "任务不存在"}}

        task = tasks[task_id]
        if not task.get("result_file"):
            return {"status": 404, "body": {"error": "结果尚未生成"}}

        result_path = RESULTS_DIR / task["result_file"]
        if not result_path.exists():
            return {"status": 404, "body": {"error": "结果文件不存在"}}

        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {"status": 200, "body": content, "content_type": "text/csv"}

    # GET /api/tasks — 任务列表
    if method == "GET" and path == "/api/tasks":
        tasks = load_tasks()
        return {"status": 200, "body": list(tasks.values())}

    # DELETE /api/task/{task_id} — 删除任务
    if method == "DELETE" and path.startswith("/api/task/"):
        task_id = path.split("/api/task/")[1]
        tasks = load_tasks()
        if task_id not in tasks:
            return {"status": 404, "body": {"error": "任务不存在"}}
        if tasks[task_id].get("result_file"):
            result_path = RESULTS_DIR / tasks[task_id]["result_file"]
            if result_path.exists():
                result_path.unlink()
        del tasks[task_id]
        save_tasks(tasks)
        return {"status": 200, "body": {"message": "删除成功"}}

    return {"status": 404, "body": {"error": "未找到路由"}}


async def run_task(task_id: str):
    """后台执行采集"""
    tasks = load_tasks()
    task = tasks.get(task_id, {})
    task["status"] = "running"
    save_tasks(tasks)

    try:
        from collector import XiaoHongShuCollector, Config

        config = Config(
            keywords=task.get("keywords", []),
            max_scroll=task.get("max_scroll", 20),
            headless=True,
            output_format=task.get("format", "csv"),
            output_path="",
        )

        result_filename = f"result_{task_id}_{int(time.time())}.{config.output_format}"
        result_path = RESULTS_DIR / result_filename
        config.output_path = str(result_path)

        async with XiaoHongShuCollector(config) as collector:
            await collector.collect()

        task["status"] = "completed"
        task["completed_at"] = time.time()
        task["total_found"] = len(collector.results)
        task["result_file"] = result_filename
        save_tasks(tasks)

    except Exception as e:
        task["status"] = "failed"
        task["completed_at"] = time.time()
        task["error"] = str(e)
        save_tasks(tasks)


# ============================================================
# HTTP 服务器 (基于内置 http.server)
# ============================================================

import json as json_module
from http.server import HTTPServer, BaseHTTPRequestHandler


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = parse_request("GET", self.path, None)
        self._respond(result)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        result = parse_request("POST", self.path, body)
        self._respond(result)

    def do_DELETE(self):
        result = parse_request("DELETE", self.path, None)
        self._respond(result)

    def _respond(self, result: dict):
        status = result.get("status", 500)
        body = result.get("body", {"error": "内部错误"})
        content_type = result.get("content_type", "application/json")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        if isinstance(body, (dict, list)):
            self.wfile.write(json_module.dumps(body, ensure_ascii=False).encode())
        elif isinstance(body, str):
            self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[API] {args[0]} {args[1]} {args[2]}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="小红书账号采集API服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", "-p", type=int, default=8000, help="监听端口")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), APIHandler)
    print(f"🌐 小红书账号采集API服务启动: http://{args.host}:{args.port}")
    print(f"   POST  /api/task          — 创建采集任务")
    print(f"   GET   /api/tasks          — 查看任务列表")
    print(f"   GET   /api/task/{{id}}     — 查询任务状态")
    print(f"   GET   /api/task/{{id}}/result — 下载结果")
    print(f"   DELETE /api/task/{{id}}    — 删除任务")
    print()
    server.serve_forever()


if __name__ == "__main__":
    main()
