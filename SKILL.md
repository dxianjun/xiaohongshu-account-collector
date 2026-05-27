---
name: xiaohongshu-account-collector
description: 小红书行业账号ID采集工具。按行业关键词采集小红书用户账号ID和主页链接。支持四种使用方式：(1) CLI脚本，(2) Web管理页面，(3) 独立API服务，(4) Agent skill调用。输出格式支持CSV/JSON/Markdown。使用场景：竞品账号采集、行业KOL挖掘、客户指定行业账号收集。
---

# 小红书行业账号ID采集工具

## 概述

按关键词搜索小红书用户，采集账号ID和主页链接，支持去重和批量导出。

**输出数据**: `user_id`（用户标识）+ `profile_url`（主页链接）
**输出格式**: CSV / JSON / Markdown 表格

## 四种使用方式

### 方式1: Web管理页面 (推荐运营使用)

```bash
cd <base_dir>/scripts
pip install fastapi uvicorn playwright
playwright install chromium
python web_service.py
# 浏览器访问 http://localhost:8000
```

功能：输入关键词 → 创建任务 → 实时进度 → 下载CSV结果

### 方式2: CLI命令行

```bash
cd <base_dir>/scripts
pip install playwright
playwright install chromium

# CSV输出（默认）
python collector.py --keywords "健身,瑜伽" --output result.csv

# Markdown输出
python collector.py --keywords "健身" --format md --output result.md

# JSON输出
python collector.py --keywords-file keywords.txt --format json --output result.json
```

### 方式3: 独立API服务 (供外部系统调用)

```bash
cd <base_dir>/scripts
python api_server.py --port 8000
```

API端点：
```
POST   /api/task              — 创建采集任务
GET    /api/tasks             — 任务列表
GET    /api/task/{id}         — 查询任务状态
GET    /api/task/{id}/result  — 下载结果
DELETE /api/task/{id}         — 删除任务
```

调用示例：
```bash
curl -X POST http://localhost:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["健身", "瑜伽"], "format": "csv"}'
```

### 方式4: Agent skill调用

```python
from <base_dir>/scripts.collector import XiaoHongShuCollector, Config

config = Config(keywords=["健身", "瑜伽"])
async with XiaoHongShuCollector(config) as collector:
    await collector.collect()
```

## 核心参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keywords` / `-k` | 关键词，逗号分隔 | 必填 |
| `--keywords-file` | 关键词文件（每行一个） | - |
| `--output` / `-o` | 输出文件路径 | `result.csv` |
| `--format` / `-f` | 输出格式: csv/json/md | csv |
| `--max-scroll` | 每个关键词最大翻页次数 | 20 |
| `--no-headless` | 显示浏览器窗口（调试用） | headless |
| `--cookie-file` | Cookie文件路径 | `cookies.json` |

## 反爬策略

- 随机User-Agent切换
- 请求间隔随机化（2~5秒）
- 浏览器指纹反检测
- Cookie持久化（登录后可复用）
- 多账号轮换支持（待完善）

## 注意事项

1. **首次使用需要登录**: 可手动登录后导出cookies.json
2. **采集频率控制**: 默认延迟已做随机化，建议不要调太低
3. **账号安全**: 建议使用小号采集，避免主号被限流
4. **结果去重**: 系统自动对user_id去重，同一用户不会重复采集

## 文件结构

```
<base_dir>/
├── SKILL.md
└── scripts/
    ├── collector.py       # 核心采集引擎
    ├── web_service.py     # Web管理服务（FastAPI）
    └── api_server.py      # 独立API服务（无框架依赖）
```
