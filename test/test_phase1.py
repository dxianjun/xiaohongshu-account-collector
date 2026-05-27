#!/usr/bin/env python3
"""
TASK-005 Phase1 自动化测试脚本
测试 collector.py 的 CLI 参数解析、引擎初始化、输出格式化等
"""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

# 添加 collector 模块路径
SCRIPTS = Path("/app/skills/xiaohongshu-account-collector/scripts")
sys.path.insert(0, str(SCRIPTS))

# ============================================================
# TC-001 & TC-002: CLI 参数解析
# ============================================================

class TestCLIArgs(unittest.TestCase):
    """TC-001: CLI 参数解析"""

    def setUp(self):
        # 保存原始 argv
        self._orig_argv = sys.argv

    def tearDown(self):
        sys.argv = self._orig_argv

    def test_basic_keywords(self):
        """--keywords 逗号分隔正确解析"""
        sys.argv = ["collector.py", "--keywords", "健身,瑜伽", "--output", "test.csv"]
        from collector import parse_args, load_keywords
        args = parse_args()
        keywords = load_keywords(args)
        self.assertEqual(keywords, ["健身", "瑜伽"])

    def test_single_keyword(self):
        """单个关键词"""
        sys.argv = ["collector.py", "-k", "健身"]
        from collector import parse_args, load_keywords
        args = parse_args()
        keywords = load_keywords(args)
        self.assertEqual(keywords, ["健身"])

    def test_default_values(self):
        """默认值检查"""
        sys.argv = ["collector.py", "--keywords", "健身"]
        from collector import parse_args
        args = parse_args()
        self.assertEqual(args.format, "csv")
        self.assertEqual(args.max_scroll, 20)
        self.assertTrue(args.headless)
        self.assertEqual(args.output, "result.csv")
        self.assertEqual(args.cookie_file, "cookies.json")

    def test_no_headless(self):
        """--no-headless 关闭无头模式"""
        sys.argv = ["collector.py", "--keywords", "健身", "--no-headless"]
        from collector import parse_args
        args = parse_args()
        self.assertFalse(args.headless)

    def test_output_format(self):
        """输出格式设置"""
        for fmt in ["csv", "json", "md"]:
            sys.argv = ["collector.py", "--keywords", "健身", "--format", fmt]
            from collector import parse_args
            args = parse_args()
            self.assertEqual(args.format, fmt)

    def test_custom_output(self):
        """自定义输出路径"""
        sys.argv = ["collector.py", "--keywords", "健身", "--output", "my_result.csv"]
        from collector import parse_args, load_keywords
        args = parse_args()
        self.assertEqual(args.output, "my_result.csv")


class TestCLIKeywordsFile(unittest.TestCase):
    """TC-002: 关键词文件加载"""

    def setUp(self):
        self._orig_argv = sys.argv
        # 创建临时关键词文件
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
        self.tmpfile.write("健身\n瑜伽\n减脂餐\n")
        self.tmpfile.close()

    def tearDown(self):
        sys.argv = self._orig_argv
        if os.path.exists(self.tmpfile.name):
            os.unlink(self.tmpfile.name)

    def test_keywords_file(self):
        """从文件读取关键词"""
        sys.argv = ["collector.py", "--keywords-file", self.tmpfile.name]
        from collector import load_keywords
        args = type('Args', (), {'keywords': None, 'keywords_file': self.tmpfile.name})()
        keywords = load_keywords(args)
        self.assertEqual(keywords, ["健身", "瑜伽", "减脂餐"])

    def test_merge_both(self):
        """同时提供--keywords和--keywords-file"""
        sys.argv = ["collector.py", "--keywords", "跑步", "--keywords-file", self.tmpfile.name]
        from collector import load_keywords
        args = type('Args', (), {'keywords': "跑步", 'keywords_file': self.tmpfile.name})()
        keywords = load_keywords(args)
        self.assertIn("跑步", keywords)
        self.assertIn("健身", keywords)
        self.assertIn("瑜伽", keywords)
        self.assertEqual(len(keywords), 4)  # 跑步 + 3个文件中的


class TestConfig(unittest.TestCase):
    """TC-003: 核心引擎配置与初始化"""

    def test_config_defaults(self):
        """Config 默认值"""
        from collector import Config
        config = Config(keywords=["健身"])
        self.assertEqual(config.keywords, ["健身"])
        self.assertEqual(config.max_scroll, 20)
        self.assertEqual(config.min_delay, 2.0)
        self.assertEqual(config.max_delay, 5.0)
        self.assertTrue(config.headless)
        self.assertEqual(config.output_format, "csv")
        self.assertEqual(config.output_path, "result.csv")
        self.assertEqual(config.cookie_file, "cookies.json")

    def test_config_custom(self):
        """Config 自定义值"""
        from collector import Config
        config = Config(
            keywords=["健身"],
            max_scroll=10,
            headless=False,
            output_format="json",
            output_path="/tmp/test.json",
            cookie_file="/tmp/cookies.json",
            min_delay=1.0,
            max_delay=3.0,
        )
        self.assertEqual(config.max_scroll, 10)
        self.assertFalse(config.headless)
        self.assertEqual(config.output_format, "json")

    def test_collector_init(self):
        """Collector 初始化状态"""
        from collector import XiaoHongShuCollector, Config
        config = Config(keywords=["健身"])
        collector = XiaoHongShuCollector(config)
        self.assertEqual(collector.config, config)
        self.assertEqual(collector.results, [])
        self.assertEqual(collector.seen_ids, set())


class TestExtractUserID(unittest.TestCase):
    """TC-004: 用户ID提取"""

    def setUp(self):
        from collector import XiaoHongShuCollector, Config
        self.collector = XiaoHongShuCollector(Config(keywords=[]))

    def test_standard_url(self):
        """标准小红书URL"""
        url = "https://www.xiaohongshu.com/user/profile/5f8a1b2c3d4e"
        uid = self.collector._extract_user_id(url)
        self.assertEqual(uid, "5f8a1b2c3d4e")

    def test_url_with_params(self):
        """带查询参数的URL"""
        url = "https://www.xiaohongshu.com/user/profile/abc123?source=web"
        uid = self.collector._extract_user_id(url)
        self.assertEqual(uid, "abc123")

    def test_xhslink(self):
        """xhslink 短链接"""
        url = "https://xhslink.com/xyz789"
        uid = self.collector._extract_user_id(url)
        self.assertEqual(uid, "xyz789")

    def test_empty_url(self):
        """空URL"""
        uid = self.collector._extract_user_id("")
        self.assertEqual(uid, "")

    def test_invalid_url(self):
        """不匹配的URL"""
        uid = self.collector._extract_user_id("https://example.com/not/user/profile")
        self.assertEqual(uid, "")

    def test_none_url(self):
        uid = self.collector._extract_user_id(None)
        self.assertEqual(uid, "")


class TestOutputFormat(unittest.TestCase):
    """TC-005: 输出格式化"""

    def setUp(self):
        from collector import XiaoHongShuCollector, Config
        self.collector = XiaoHongShuCollector(Config(keywords=["健身"]))
        # 注入测试数据
        self.collector.results = [
            {"user_id": "uid_001", "nickname": "健身达人", "profile_url": "https://www.xiaohongshu.com/user/profile/uid_001", "source_keyword": "健身"},
            {"user_id": "uid_002", "nickname": "瑜伽教练", "profile_url": "https://www.xiaohongshu.com/user/profile/uid_002", "source_keyword": "瑜伽"},
        ]

    def test_csv_output(self):
        """CSV输出"""
        from collector import XiaoHongShuCollector, Config
        collector = XiaoHongShuCollector(Config(keywords=["健身"]))
        collector.results = self.collector.results

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', newline='', encoding='utf-8-sig') as f:
            output_path = f.name

        collector.config.output_path = output_path
        collector.config.output_format = "csv"
        collector._save_results()

        with open(output_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        # 检查BOM和内容
        self.assertIn("user_id", content)
        self.assertIn("uid_001", content)
        self.assertIn("uid_002", content)
        self.assertIn("健身达人", content)

        os.unlink(output_path)

    def test_json_output(self):
        """JSON输出"""
        from collector import XiaoHongShuCollector, Config
        collector = XiaoHongShuCollector(Config(keywords=["健身"]))
        collector.results = self.collector.results

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w', encoding='utf-8') as f:
            output_path = f.name

        collector.config.output_path = output_path
        collector.config.output_format = "json"
        collector._save_results()

        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["user_id"], "uid_001")
        self.assertEqual(data[1]["nickname"], "瑜伽教练")

        os.unlink(output_path)

    def test_markdown_output(self):
        """Markdown输出"""
        from collector import XiaoHongShuCollector, Config
        collector = XiaoHongShuCollector(Config(keywords=["健身"]))
        collector.results = self.collector.results

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode='w', encoding='utf-8') as f:
            output_path = f.name

        collector.config.output_path = output_path
        collector.config.output_format = "md"
        collector._save_results()

        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("用户ID", content)
        self.assertIn("uid_001", content)
        self.assertIn("健身达人", content)
        self.assertIn("|", content)  # 表格格式

        os.unlink(output_path)

    def test_empty_results(self):
        """空结果输出"""
        from collector import XiaoHongShuCollector, Config
        collector = XiaoHongShuCollector(Config(keywords=["健身"]))
        # 空结果

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode='w', newline='', encoding='utf-8-sig') as f:
            output_path = f.name

        collector.config.output_path = output_path
        collector.config.output_format = "csv"
        collector._save_results()

        with open(output_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        self.assertIn("user_id", content)  # 应有表头

        os.unlink(output_path)


# ============================================================
# Web服务测试
# ============================================================

class TestWebService(unittest.TestCase):
    """TC-006: Web服务路由"""

    @classmethod
    def setUpClass(cls):
        """启动测试服务"""
        # 使用 FastAPI TestClient
        from fastapi.testclient import TestClient
        from web_service import app
        cls.client = TestClient(app)

    def test_index_page(self):
        """GET / 返回HTML"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("小红书", response.text)

    def test_create_task(self):
        """POST /api/task 创建任务"""
        response = self.client.post("/api/task", json={
            "keywords": ["健身", "瑜伽"],
            "max_scroll": 10
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["keywords"], ["健身", "瑜伽"])
        return data["task_id"]

    def test_create_task_empty_keywords(self):
        """空关键词返回400"""
        response = self.client.post("/api/task", json={"keywords": []})
        self.assertEqual(response.status_code, 400)

    def test_get_tasks(self):
        """GET /api/tasks 返回列表"""
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        tasks = response.json()
        self.assertIsInstance(tasks, list)

    def test_get_task_not_found(self):
        """不存在的task_id返回404"""
        response = self.client.get("/api/task/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_delete_task(self):
        """DELETE /api/task/{id}"""
        # 先创建
        create_resp = self.client.post("/api/task", json={"keywords": ["测试删除"]})
        task_id = create_resp.json()["task_id"]

        # 再删除
        delete_resp = self.client.delete(f"/api/task/{task_id}")
        self.assertEqual(delete_resp.status_code, 200)

        # 验证已删除
        get_resp = self.client.get(f"/api/task/{task_id}")
        self.assertEqual(get_resp.status_code, 404)

    def test_task_status_flow(self):
        """TC-007: 任务状态流转"""
        # 创建 -> pending
        resp = self.client.post("/api/task", json={"keywords": ["状态测试"]})
        task = resp.json()
        self.assertEqual(task["status"], "pending")
        task_id = task["task_id"]

        # 查询 -> pending 或 running
        resp = self.client.get(f"/api/task/{task_id}")
        task = resp.json()
        self.assertIn(task["status"], ["pending", "running", "completed"])

    def test_cors_headers(self):
        """TC-009: CORS头"""
        # CORS middleware 在 TestClient 下可能不触发 Set-CORS 头
        # 采用代码审计方式验证配置
        from web_service import app as ws_app
        from fastapi.middleware.cors import CORSMiddleware
        # 检查是否注册了CORS中间件
        cors_middleware = [m for m in ws_app.user_middleware if m.cls == CORSMiddleware]
        self.assertTrue(len(cors_middleware) > 0, "CORS 中间件未注册")
        # 验证 OPTIONS 路由存在 (FastAPI自动注册)
        response = self.client.options("/api/task")
        self.assertIn(response.status_code, [200, 405])  # 405 表示路由存在但没有OPTIONS handler，这是正常的


class TestWebServiceKeywords(unittest.TestCase):
    """TC-008: 关键词输入处理"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from web_service import app
        cls.client = TestClient(app)

    def test_newline_keywords(self):
        """换行分隔 (前端已处理, API接收的是数组)"""
        response = self.client.post("/api/task", json={
            "keywords": ["健身", "瑜伽", "减脂餐"]
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["keywords"], ["健身", "瑜伽", "减脂餐"])

    def test_single_keyword(self):
        """单个关键词"""
        response = self.client.post("/api/task", json={
            "keywords": ["健身"]
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["keywords"], ["健身"])


# ============================================================
# 独立API服务测试
# ============================================================

class TestAPIServer(unittest.TestCase):
    """TC-010 & TC-011: 独立API服务"""

    def setUp(self):
        # 导入 api_server 的 parse_request
        from api_server import parse_request
        self.parse_request = parse_request

    def test_create_task(self):
        """POST /api/task 创建任务"""
        body = json.dumps({"keywords": ["健身", "瑜伽"]}).encode()
        result = self.parse_request("POST", "/api/task", body)
        self.assertEqual(result["status"], 200)
        data = result["body"]
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")

    def test_get_tasks(self):
        """GET /api/tasks"""
        result = self.parse_request("GET", "/api/tasks", None)
        self.assertEqual(result["status"], 200)

    def test_empty_body(self):
        """空请求体"""
        result = self.parse_request("POST", "/api/task", None)
        self.assertEqual(result["status"], 400)
        self.assertIn("error", result["body"])  # 返回的是 dict，直接检查 key

    def test_invalid_json(self):
        """无效JSON"""
        result = self.parse_request("POST", "/api/task", b"not json")
        self.assertEqual(result["status"], 400)

    def test_keywords_not_list(self):
        """keywords不是列表"""
        body = json.dumps({"keywords": "健身"}).encode()
        result = self.parse_request("POST", "/api/task", body)
        self.assertEqual(result["status"], 400)

    def test_keywords_empty(self):
        """keywords为空列表"""
        body = json.dumps({"keywords": []}).encode()
        result = self.parse_request("POST", "/api/task", body)
        self.assertEqual(result["status"], 400)

    def test_task_not_found(self):
        """不存在的task_id"""
        result = self.parse_request("GET", "/api/task/nonexistent", None)
        self.assertEqual(result["status"], 404)

    def test_unknown_route(self):
        """未知路由"""
        result = self.parse_request("GET", "/api/unknown", None)
        self.assertEqual(result["status"], 404)


# ============================================================
# TC-012: 数据持久化
# ============================================================

class TestPersistence(unittest.TestCase):
    """TC-012: 数据持久化"""

    def setUp(self):
        from api_server import DATA_DIR, TASKS_FILE, RESULTS_DIR
        self.data_dir = DATA_DIR
        self.tasks_file = TASKS_FILE
        self.results_dir = RESULTS_DIR
        if self.tasks_file.exists():
            self.tasks_file.unlink()

    def tearDown(self):
        if self.tasks_file.exists():
            self.tasks_file.unlink()
        for f in self.results_dir.glob("*"):
            f.unlink()

    def test_tasks_json_created(self):
        """创建任务后 tasks.json 存在"""
        import json
        from api_server import parse_request
        body = json.dumps({"keywords": ["健身"]}).encode()
        result = parse_request("POST", "/api/task", body)
        self.assertEqual(result["status"], 200)
        self.assertTrue(self.tasks_file.exists(), "tasks.json 未被创建")
        with open(self.tasks_file, "r") as f:
            tasks = json.load(f)
        self.assertGreater(len(tasks), 0)

    def test_persistence_between_requests(self):
        """多次请求数据持久化"""
        import json
        from api_server import parse_request, load_tasks
        body = json.dumps({"keywords": ["健身"]}).encode()
        result = parse_request("POST", "/api/task", body)
        task_id = result["body"]["task_id"]
        tasks = load_tasks()
        self.assertIn(task_id, tasks)
        self.assertEqual(tasks[task_id]["keywords"], ["健身"])


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TASK-005 Phase1 自动化测试")
    print("=" * 60)
    unittest.main(verbosity=2)
