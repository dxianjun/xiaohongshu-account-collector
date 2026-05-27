# 小红书行业账号ID采集工具

> 按行业关键词采集小红书用户账号ID和主页链接，支持 CLI / Web / API 三种使用模式。

## ✨ 功能特性

- 🔍 **多关键词采集** — 逗号分隔、换行、文件导入三种输入方式
- 📋 **三种使用模式** — CLI命令行 / Web管理页面 / 独立API服务
- 📁 **三格式输出** — CSV(含BOM，兼容Excel)、JSON、Markdown
- 🛡️ **反爬策略** — UA随机切换、请求延迟随机化、Cookie复用
- 🔄 **去重机制** — 自动避免重复采集同一用户
- 🚫 **错误隔离** — 单个关键词失败不影响整体任务

## 🚀 快速开始

### 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 模式一：CLI 命令行

```bash
# 单批关键词采集
python scripts/collector.py --keywords "健身,瑜伽,跑步" --format csv --output results.csv

# 从文件读取关键词
python scripts/collector.py --keywords-file keywords.txt --format json --output results.json

# Markdown 格式输出
python scripts/collector.py --keywords "健身教练" --format md --output results.md
```

### 模式二：Web 管理页面

```bash
python scripts/web_service.py
```

浏览器访问 `http://localhost:8000`，通过可视化界面：
- 输入/管理关键词
- 启动采集任务
- 预览和导出结果

### 模式三：API 服务

```bash
python scripts/api_server.py --port 8000
```

API 端点：

| 方法 | 路径 | 说明 |
|:----:|------|------|
| POST | `/api/task` | 创建采集任务 |
| GET | `/api/task/{task_id}` | 查询任务状态 |
| GET | `/api/task/{task_id}/result` | 获取采集结果 |
| GET | `/api/tasks` | 查看所有任务 |

### Cookie 配置

首次使用需要登录小红书，将 Cookies 保存为 `cookies.json` 文件放在运行目录：

```json
{
  "cookies": [
    {"name": "a1", "value": "xxx", "domain": ".xiaohongshu.com", ...},
    ...
  ]
}
```

## 📚 文档

- [PRD 产品需求文档](docs/PRD.md)
- [技术方案文档](docs/PLAN.md)
- [测试用例](docs/test_cases.md)
- [测试报告](docs/test_report.md)
- [验收报告 v1.0](docs/acceptance_report.md)

## 📁 项目结构

```
xiaohongshu-account-collector/
├── scripts/              # 核心代码
│   ├── collector.py      # CLI采集工具
│   ├── web_service.py    # Web管理页面
│   └── api_server.py     # API服务
├── test/                 # 测试脚本
│   └── test_phase1.py    # 41个测试用例
├── docs/                 # 项目文档
│   ├── PRD.md
│   ├── PLAN.md
│   ├── test_cases.md
│   ├── test_report.md
│   └── acceptance_report.md
├── SKILL.md              # Skill 配置文档
├── requirements.txt
└── .gitignore
```

## 🔧 技术栈

- **Python 3.10+** — 主开发语言
- **Playwright** — 浏览器自动化采集
- **FastAPI** — API 服务框架
- **aiofiles** — 异步文件操作

## 📌 版本说明

### v1.0 (当前版本)
- ✅ 多关键词批量搜索采集
- ✅ 用户ID自动提取（URL + 短链接）
- ✅ CLI / Web / API 三种模式
- ✅ CSV / JSON / Markdown 三格式输出
- ✅ 反爬策略（UA + 延迟 + Cookie复用）
- ✅ 错误隔离与去重

### Phase 2 (规划中)
- ⏳ 社交链路挖掘（关注/粉丝/标签链）
- ⏳ 话题/标签页遍历
- ⏳ 简介、粉丝数、笔记数字段提取
- ⏳ 纯 API 模式降级

## 📄 许可证

MIT
