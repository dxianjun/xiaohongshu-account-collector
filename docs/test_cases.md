# TASK-005 小红书行业账号ID采集工具 — Phase1 测试用例

**测试时间**: 2026-05-28
**测试对象**: xiaohongshu-account-collector (v1.0.0)
**测试范围**: 单元测试 + 模块集成测试

---

## 测试模块划分

| 模块 | 文件 | 优先级 |
|------|------|:------:|
| 核心采集引擎 | `collector.py` | P0 |
| Web管理服务 | `web_service.py` | P0 |
| 独立API服务 | `api_server.py` | P1 |
| CLI参数解析 | `collector.py::parse_args` | P0 |

---

## TC-001: CLI 参数解析 — 基本参数

### 验证项
- [ ] `--keywords "健身,瑜伽"` 正确解析关键词列表
- [ ] `--output result.xlsx` 正确设置输出路径
- [ ] `--format csv|json|md` 正确设置格式
- [ ] 默认值正确（headless=True, max_scroll=20, format=csv）
- [ ] `--no-headless` 正确关闭无头模式

## TC-002: CLI 参数解析 — 关键词文件加载

### 验证项
- [ ] `--keywords-file keywords.txt` 正确读取文件
- [ ] 同时提供 `--keywords` 和 `--keywords-file` 合并去重
- [ ] 无关键词时输出错误提示并退出（exit code 1）

## TC-003: 核心引擎对象初始化

### 验证项
- [ ] `Config` dataclass 默认值正确
- [ ] Config 支持自定义覆盖
- [ ] Collector 初始化时 results/seen_ids 为空

## TC-004: _extract_user_id 方法

### 验证项
- [ ] `https://www.xiaohongshu.com/user/profile/5f8a1b2c3d4e` → `5f8a1b2c3d4e`
- [ ] `https://xhslink.com/abc123` → `abc123`
- [ ] 空字符串/不匹配URL → `""`
- [ ] 带查询参数的URL正确提取

## TC-005: 输出格式化

### 验证项
- [ ] CSV 输出正确含 BOM (utf-8-sig)
- [ ] CSV 列名: user_id, nickname, profile_url, source_keyword
- [ ] JSON 输出格式正确，缩进2空格
- [ ] Markdown 输出格式正确，含表格头
- [ ] 空结果输出正确（无数据时）

## TC-006: Web服务 — FastAPI 路由

### 验证项
- [ ] GET `/` 返回 HTML 管理页面
- [ ] POST `/api/task` 创建任务返回 task_id
- [ ] GET `/api/tasks` 返回任务列表
- [ ] GET `/api/task/{id}` 返回单个任务状态
- [ ] GET `/api/task/{id}/result` 下载结果
- [ ] DELETE `/api/task/{id}` 删除任务
- [ ] 无效 task_id 返回 404

## TC-007: Web服务 — 任务状态流转

### 验证项
- [ ] 新建任务 status=pending
- [ ] 开始采集 status=running
- [ ] 采集完成 status=completed
- [ ] 采集失败 status=failed
- [ ] 状态更新持久化到 tasks.json

## TC-008: Web服务 — 关键词输入处理

### 验证项
- [ ] 空关键词返回 400
- [ ] 换行分隔正常处理
- [ ] 逗号分隔正常处理
- [ ] 混合分隔正常处理
- [ ] 中英文逗号兼容

## TC-009: Web服务 — CORS 头

### 验证项
- [ ] 响应含 `Access-Control-Allow-Origin: *`
- [ ] 响应含 `Access-Control-Allow-Methods`
- [ ] OPTIONS 请求正常返回 200

## TC-010: 独立API服务 — HTTP路由

### 验证项
- [ ] POST `/api/task` 创建任务
- [ ] GET `/api/tasks` 返回列表
- [ ] GET `/api/task/{id}` 查询状态
- [ ] GET `/api/task/{id}/result` 下载结果
- [ ] DELETE `/api/task/{id}` 删除任务
- [ ] 未知路由返回 404

## TC-011: 独立API服务 — 错误处理

### 验证项
- [ ] 空请求体返回 400
- [ ] 无效JSON返回 400
- [ ] keywords不是列表返回 400
- [ ] keywords为空列表返回 400
- [ ] 不存在的task_id返回 404

## TC-012: 数据持久化

### 验证项
- [ ] tasks.json 存在且格式正确
- [ ] 结果文件写入 results/ 目录
- [ ] 删除任务同时清理结果文件
- [ ] 重启保持数据不丢失

---

## 统计

- 总用例数: 12
- P0: TC-001 ~ TC-009
- P1: TC-010 ~ TC-012
