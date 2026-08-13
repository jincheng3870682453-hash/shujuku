# -*- coding: utf-8 -*-
"""
AI 客户端与 AI 请求解析单元测试

覆盖：
- AIClient._friendly_web_search_error：联网搜索错误提示的命中与放行
- AIClient._extract_response_content：联网搜索 tool_calls 场景的正文提取
- AIClient._build_messages：操作日志时间戳字段（created_at）的正确使用
- AIClient._extract_api_error：服务商错误响应的提取与格式化
- app._parse_ai_request：provider + base_url 双重判断联网搜索开关
- app._attach_warning / _safe_close：辅助函数

运行方式:
    cd backend
    python -m pytest test_ai_client.py -v
    或
    python test_ai_client.py
"""

import os
import sys
import unittest

# 确保项目根目录可以被导入（app 位于项目根目录）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai_client import AIClient

# 导入 app 顶层会打印启动信息并创建 backups 目录，但不会启动服务器
from app import (
    app as flask_app,
    _parse_ai_request,
    _attach_warning,
    _safe_close,
)


# ========== _friendly_web_search_error ==========


class TestFriendlyWebSearchError(unittest.TestCase):
    """联网搜索不支持时，应转换为可操作提示"""

    def test_unknown_variant(self):
        """OpenAI 严格 schema 报错：unknown variant `web_search`"""
        raw = "Failed to deserialize request body. unknown variant `web_search`, expected `function`"
        result = AIClient._friendly_web_search_error(raw)
        self.assertIn("联网搜索", result)
        self.assertIn("DeepSeek", result)

    def test_not_a_valid_tool(self):
        """中转端点报错：'web_search' is not a valid tool type"""
        raw = "Invalid 'tools[0]': 'web_search' is not a valid tool type."
        result = AIClient._friendly_web_search_error(raw)
        self.assertIn("联网搜索", result)

    def test_not_one_of_accepted_values(self):
        """中转端点报错：'web_search' is not one of the accepted values"""
        raw = "'web_search' is not one of the accepted values: ['function']"
        result = AIClient._friendly_web_search_error(raw)
        self.assertIn("联网搜索", result)

    def test_rate_limit_passthrough(self):
        """与联网搜索无关的错误应原样返回"""
        raw = "Rate limit exceeded. Please try again later."
        self.assertEqual(AIClient._friendly_web_search_error(raw), raw)

    def test_web_search_without_keywords_passthrough(self):
        """含 web_search 但不匹配任何关键字时原样返回（避免误伤）"""
        raw = "web_search feature is not supported by this endpoint"
        self.assertEqual(AIClient._friendly_web_search_error(raw), raw)

    def test_case_insensitive(self):
        """错误文本大小写混合时仍应命中"""
        raw = "Unknown Variant `Web_Search`, Expected `Function`"
        result = AIClient._friendly_web_search_error(raw)
        self.assertIn("联网搜索", result)


# ========== _extract_response_content ==========


class TestExtractResponseContent(unittest.TestCase):
    """从非流式响应 message 中提取正文"""

    def test_normal_content(self):
        """有 content 时直接返回"""
        message = {"role": "assistant", "content": "这是一份分析报告"}
        self.assertEqual(AIClient._extract_response_content(message), "这是一份分析报告")

    def test_empty_content_with_tool_calls(self):
        """content 为空但存在 tool_calls（联网搜索已执行）时拼装可读文本"""
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "2025年GDP"}'},
                }
            ],
        }
        result = AIClient._extract_response_content(message)
        self.assertIn("联网搜索", result)
        self.assertIn("web_search", result)

    def test_empty_content_with_invalid_args_json(self):
        """tool_calls 的 arguments 不是合法 JSON 时不应抛异常"""
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": "web_search", "arguments": "{bad json"}}
            ],
        }
        result = AIClient._extract_response_content(message)
        self.assertIn("联网搜索", result)

    def test_empty_content_no_tool_calls(self):
        """content 与 tool_calls 均为空时返回空字符串"""
        message = {"role": "assistant", "content": ""}
        self.assertEqual(AIClient._extract_response_content(message), "")

    def test_missing_content_key(self):
        """message 缺少 content 键时返回空字符串"""
        message = {"role": "assistant"}
        self.assertEqual(AIClient._extract_response_content(message), "")


# ========== _build_messages ==========


class TestBuildMessages(unittest.TestCase):
    """分析 Prompt 构建"""

    def setUp(self):
        self.client = AIClient(
            provider="openai", model="gpt-4o-mini", api_key="sk-test"
        )

    def test_log_timestamp_uses_created_at(self):
        """操作日志应使用 created_at 字段（数据库实际字段名）"""
        data_summary = {
            "total_rows": 10,
            "total_columns": 3,
            "columns": [],
            "recent_logs": [
                {
                    "created_at": "2026-08-13 10:00:00",
                    "username": "admin",
                    "role": "管理员",
                    "action": "登录",
                    "detail": "登录成功",
                }
            ],
        }
        messages = self.client._build_messages(data_summary)
        user_content = messages[1]["content"]
        self.assertIn("2026-08-13 10:00:00", user_content)

    def test_message_structure(self):
        """返回 system + user + user 三段结构"""
        messages = self.client._build_messages(
            {"total_rows": 1, "total_columns": 1, "columns": [], "recent_logs": []}
        )
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[2]["role"], "user")

    def test_default_question(self):
        """未传 question 时使用默认提问"""
        messages = self.client._build_messages(
            {"total_rows": 1, "total_columns": 1, "columns": [], "recent_logs": []}
        )
        self.assertIn("全面分析", messages[2]["content"])

    def test_user_context_injects_role_and_permissions(self):
        """传入 user_context 时，system prompt 应包含用户身份与权限边界"""
        messages = self.client._build_messages(
            {"total_rows": 1, "total_columns": 1, "columns": [], "recent_logs": []},
            user_context={
                "username": "employee",
                "role": "employee",
                "permissions": ["view_data", "search_data"],
            },
        )
        system_content = messages[0]["content"]
        self.assertIn("employee", system_content)
        self.assertIn("员工", system_content)
        self.assertIn("view_data", system_content)
        self.assertIn("权限边界", system_content)

    def test_user_context_no_permissions(self):
        """无权限列表时提示词给出兜底描述"""
        messages = self.client._build_messages(
            {"total_rows": 1, "total_columns": 1, "columns": [], "recent_logs": []},
            user_context={"username": "u", "role": "custom"},
        )
        system_content = messages[0]["content"]
        self.assertIn("无额外权限", system_content)
        self.assertIn("权限边界", system_content)

    def test_analyze_passes_user_context(self):
        """analyze() 应把 user_context 透传给 _build_messages"""
        client = AIClient(provider="openai", model="gpt-4o-mini", api_key="sk-test")

        class _FakeCaller:
            def __init__(self):
                self.received = None

            def __call__(self, messages, stream, fail_prefix):
                self.received = messages
                return {"success": True, "content": "ok", "tokens": {}}

        fake = _FakeCaller()
        original = client._call_with_errors
        client._call_with_errors = fake  # type: ignore[method-assign]

        try:
            client.analyze(
                {"total_rows": 1, "total_columns": 1, "columns": [], "recent_logs": []},
                user_context={"username": "hr", "role": "hr", "permissions": ["view_stats"]},
            )
        finally:
            client._call_with_errors = original  # type: ignore[method-assign]

        system_content = fake.received[0]["content"]
        self.assertIn("hr", system_content)
        self.assertIn("HR", system_content)


# ========== DeepSeek Responses API ==========


class TestResponsesApiRouting(unittest.TestCase):
    """_use_responses_api / _responses_endpoint_url 路由判断"""

    def test_deepseek_with_web_search_uses_responses(self):
        c = AIClient(provider="deepseek", model="deepseek-chat",
                     api_key="sk", web_search=True)
        self.assertTrue(c._use_responses_api())

    def test_deepseek_without_web_search_uses_chat_completions(self):
        c = AIClient(provider="deepseek", model="deepseek-chat",
                     api_key="sk", web_search=False)
        self.assertFalse(c._use_responses_api())

    def test_openai_with_web_search_does_not_use_responses(self):
        """OpenAI 即使 web_search=True 也不走 Responses API（前端会先关闭）"""
        c = AIClient(provider="openai", model="gpt-4o-mini",
                     api_key="sk", web_search=True)
        self.assertFalse(c._use_responses_api())

    def test_url_strips_v1_suffix(self):
        c = AIClient(provider="deepseek", model="deepseek-chat",
                     api_key="sk", base_url="https://api.deepseek.com/v1")
        self.assertEqual(c._responses_endpoint_url(), "https://api.deepseek.com/responses")

    def test_url_keeps_path_without_v1(self):
        c = AIClient(provider="deepseek", model="deepseek-chat",
                     api_key="sk", base_url="https://api.deepseek.com")
        self.assertEqual(c._responses_endpoint_url(), "https://api.deepseek.com/responses")

    def test_url_strips_v2_suffix(self):
        c = AIClient(provider="deepseek", model="deepseek-chat",
                     api_key="sk", base_url="https://example.com/v2/")
        self.assertEqual(c._responses_endpoint_url(), "https://example.com/responses")


class TestBuildResponsesPayload(unittest.TestCase):
    """_build_responses_payload 请求体构造"""

    def setUp(self):
        self.client = AIClient(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk",
            base_url="https://api.deepseek.com/v1",
            web_search=True,
        )

    def test_system_becomes_instructions(self):
        payload = self.client._build_responses_payload(
            [
                {"role": "system", "content": "你是助手"},
                {"role": "user", "content": "你好"},
            ],
            stream=False,
        )
        self.assertEqual(payload["instructions"], "你是助手")
        self.assertEqual(payload["input"], [{"role": "user", "content": "你好"}])

    def test_includes_web_search_tool(self):
        payload = self.client._build_responses_payload(
            [{"role": "user", "content": "查天气"}], stream=False,
        )
        self.assertEqual(payload["tools"], [{"type": "web_search"}])
        self.assertEqual(payload["tool_choice"], "auto")

    def test_without_web_search_omits_tools(self):
        self.client.web_search = False
        payload = self.client._build_responses_payload(
            [{"role": "user", "content": "你好"}], stream=False,
        )
        self.assertNotIn("tools", payload)
        self.assertNotIn("tool_choice", payload)

    def test_multi_turn_input_preserved(self):
        payload = self.client._build_responses_payload(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
            ],
            stream=False,
        )
        self.assertEqual(payload["input"], [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
        ])
        self.assertEqual(payload["instructions"], "sys")

    def test_stream_flag(self):
        payload_stream = self.client._build_responses_payload(
            [{"role": "user", "content": "hi"}], stream=True,
        )
        self.assertTrue(payload_stream["stream"])
        payload_no_stream = self.client._build_responses_payload(
            [{"role": "user", "content": "hi"}], stream=False,
        )
        self.assertFalse(payload_no_stream["stream"])

    def test_model_and_temperature(self):
        payload = self.client._build_responses_payload(
            [{"role": "user", "content": "hi"}], stream=False,
        )
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertIn("temperature", payload)
        self.assertIn("max_output_tokens", payload)


class TestParseResponsesNonStream(unittest.TestCase):
    """_parse_responses_non_stream 非流式响应解析"""

    def setUp(self):
        self.client = AIClient(
            provider="deepseek", model="deepseek-chat", api_key="sk",
            web_search=True,
        )

    def test_output_text_collected(self):
        resp_json = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "今天北京"},
                        {"type": "output_text", "text": "天气晴"},
                    ],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "今天北京天气晴")
        self.assertEqual(result["tokens"]["prompt"], 10)
        self.assertEqual(result["tokens"]["completion"], 5)
        self.assertEqual(result["tokens"]["total"], 15)

    def test_empty_output(self):
        result = self.client._parse_responses_non_stream({"output": []})
        self.assertEqual(result["content"], "")
        self.assertTrue(result["success"])

    def test_missing_output_key(self):
        result = self.client._parse_responses_non_stream({})
        self.assertEqual(result["content"], "")
        self.assertTrue(result["success"])

    def test_non_dict_items_skipped(self):
        resp_json = {
            "output": [None, "str", {"content": [{"type": "output_text", "text": "ok"}]}]
        }
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertEqual(result["content"], "ok")

    def test_usage_missing_returns_zeros(self):
        resp_json = {"output": [{"content": [{"type": "output_text", "text": "x"}]}]}
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertEqual(result["tokens"]["prompt"], 0)
        self.assertEqual(result["tokens"]["completion"], 0)
        self.assertEqual(result["tokens"]["total"], 0)

    def test_reasoning_text_not_leaked(self):
        """思考过程（reasoning_text / summary_text）绝不能拼进正文"""
        resp_json = {
            "output": [
                {
                    "type": "reasoning",
                    "content": [
                        {"type": "reasoning_text", "text": "Let me reconsider the plan..."},
                        {"type": "summary_text", "text": "Summary of thinking steps"},
                    ],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "杭州今天小雨转阴，25-34℃。"}
                    ],
                },
            ]
        }
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertEqual(result["content"], "杭州今天小雨转阴，25-34℃。")
        self.assertNotIn("Let me reconsider", result["content"])
        self.assertNotIn("Summary of thinking", result["content"])

    def test_input_text_not_leaked(self):
        """输入回显（input_text）不应出现在正文"""
        resp_json = {
            "output": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "杭州的天气怎么样？"}],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "杭州今天有雨。"}],
                },
            ]
        }
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertEqual(result["content"], "杭州今天有雨。")

    def test_plain_text_type_still_accepted(self):
        """兼容某些端点的 type='text' 输出"""
        resp_json = {
            "output": [
                {"type": "message", "content": [{"type": "text", "text": "兼容输出"}]}
            ]
        }
        result = self.client._parse_responses_non_stream(resp_json)
        self.assertEqual(result["content"], "兼容输出")


class TestParseResponsesStream(unittest.TestCase):
    """_parse_responses_stream SSE 流式响应解析"""

    def setUp(self):
        self.client = AIClient(
            provider="deepseek", model="deepseek-chat", api_key="sk",
            web_search=True,
        )

    def _make_response(self, lines):
        """构造一个 mock response 对象"""
        class _R:
            def __init__(self, lines):
                self._lines = lines

            def iter_lines(self, decode_unicode=True):
                return iter(self._lines)

        return _R(lines)

    def test_output_text_delta(self):
        lines = [
            'data: {"type": "response.output_text.delta", "delta": "今天"}',
            'data: {"type": "response.output_text.delta", "delta": "天气晴"}',
            'data: [DONE]',
        ]
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "今天天气晴")
        self.assertTrue(result["success"])

    def test_done_terminates_parsing(self):
        lines = [
            'data: {"type": "response.output_text.delta", "delta": "ok"}',
            'data: [DONE]',
            'data: {"type": "response.output_text.delta", "delta": "should_skip"}',
        ]
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "ok")

    def test_choices_fallback_for_proxies(self):
        """部分代理仍返回 chat/completions 风格"""
        lines = [
            'data: {"choices": [{"delta": {"content": "hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
        ]
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "hello world")

    def test_invalid_json_lines_skipped(self):
        lines = [
            'data: not-json',
            'data: {"type": "response.output_text.delta", "delta": "ok"}',
        ]
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "ok")

    def test_empty_lines_skipped(self):
        lines = ["", "   ", 'data: {"type": "response.output_text.delta", "delta": "x"}']
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "x")

    def test_data_prefix_no_space(self):
        """兼容 data:（无空格）"""
        lines = ['data:{"type": "response.output_text.delta", "delta": "y"}']
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "y")

    def test_non_data_lines_skipped(self):
        lines = [
            "event: ping",
            'data: {"type": "response.output_text.delta", "delta": "z"}',
        ]
        result = self.client._parse_responses_stream(self._make_response(lines))
        self.assertEqual(result["content"], "z")


# ========== _extract_api_error ==========


class _FakeResponse:
    """模拟 requests.Response 的 status_code / json / text"""

    def __init__(self, status_code=400, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _FakeHTTPError(Exception):
    """模拟 requests.HTTPError（带 response 属性）"""

    def __init__(self, response):
        super().__init__("HTTP Error")
        self.response = response


class TestExtractApiError(unittest.TestCase):
    """从请求异常中提取服务商错误信息"""

    def test_no_response_uses_str(self):
        """异常没有 response 属性时回退到 str(e)"""
        e = ValueError("connection reset")
        self.assertEqual(AIClient._extract_api_error(e), "connection reset")

    def test_error_message_field(self):
        """服务商返回 error.message 时优先使用"""
        resp = _FakeResponse(401, {"error": {"message": "Invalid API key"}})
        e = _FakeHTTPError(resp)
        result = AIClient._extract_api_error(e)
        self.assertEqual(result, "HTTP 401: Invalid API key")

    def test_plain_message_field(self):
        """响应顶层 message 字段"""
        resp = _FakeResponse(400, {"message": "Bad request body"})
        e = _FakeHTTPError(resp)
        result = AIClient._extract_api_error(e)
        self.assertEqual(result, "HTTP 400: Bad request body")

    def test_unknown_json_body(self):
        """无 error/message 字段时输出完整 JSON"""
        resp = _FakeResponse(500, {"code": "E001"})
        e = _FakeHTTPError(resp)
        result = AIClient._extract_api_error(e)
        self.assertEqual(result, 'HTTP 500: {"code": "E001"}')

    def test_invalid_json_falls_back_to_text(self):
        """JSON 解析失败时使用响应文本"""
        resp = _FakeResponse(502, body=ValueError("bad json"), text="<html>gateway</html>")
        e = _FakeHTTPError(resp)
        result = AIClient._extract_api_error(e)
        self.assertEqual(result, "HTTP 502: <html>gateway</html>")

    def test_web_search_error_friendly(self):
        """端点不支持联网搜索的报错被转换为友好提示"""
        resp = _FakeResponse(
            400,
            {"error": {"message": "unknown variant `web_search`, expected `function`"}},
        )
        e = _FakeHTTPError(resp)
        result = AIClient._extract_api_error(e)
        self.assertIn("联网搜索", result)
        self.assertIn("关闭", result)


# ========== _parse_ai_request ==========


class TestParseAiRequest(unittest.TestCase):
    """AI 请求解析：联网搜索开关的 provider + base_url 双重判断"""

    def test_deepseek_official_keeps_web_search(self):
        """deepseek + 官方 Base URL → 保留联网搜索"""
        with flask_app.app_context():
            _, _, client, err, warning = _parse_ai_request(
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": "sk-test",
                    "base_url": "https://api.deepseek.com",
                    "web_search": True,
                }
            )
            self.assertIsNone(err)
            self.assertIsNone(warning)
            self.assertTrue(client.web_search)

    def test_deepseek_default_base_url_keeps_web_search(self):
        """deepseek + 空 Base URL（使用预设）→ 保留联网搜索"""
        with flask_app.app_context():
            _, _, client, err, warning = _parse_ai_request(
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": "sk-test",
                    "base_url": "",
                    "web_search": True,
                }
            )
            self.assertIsNone(err)
            self.assertIsNone(warning)
            self.assertTrue(client.web_search)
            self.assertIn("deepseek.com", client.base_url)

    def test_deepseek_relay_disables_web_search(self):
        """deepseek + 非官方 Base URL → 关闭 + warning"""
        with flask_app.app_context():
            _, _, client, err, warning = _parse_ai_request(
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": "sk-test",
                    "base_url": "https://api.xxx-relay.com/v1",
                    "web_search": True,
                }
            )
            self.assertIsNone(err)
            self.assertIsNotNone(warning)
            self.assertIn("已自动关闭", warning)
            self.assertFalse(client.web_search)

    def test_openai_disables_web_search(self):
        """openai + web_search → 关闭 + warning"""
        with flask_app.app_context():
            _, _, client, err, warning = _parse_ai_request(
                {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-test",
                    "base_url": "https://api.openai.com/v1",
                    "web_search": True,
                }
            )
            self.assertIsNone(err)
            self.assertIsNotNone(warning)
            self.assertFalse(client.web_search)

    def test_missing_api_key_returns_400(self):
        """缺少 API Key → 返回 400 错误响应"""
        with flask_app.app_context():
            provider, model, client, err, warning = _parse_ai_request(
                {"provider": "openai", "model": "gpt-4o-mini", "web_search": False}
            )
            self.assertIsNone(client)
            self.assertIsNotNone(err)
            response, status = err
            self.assertEqual(status, 400)
            self.assertFalse(response.json["success"])
            self.assertIn("API Key", response.json["error"])

    def test_no_web_search_unaffected(self):
        """未开启 web_search → 不受影响"""
        with flask_app.app_context():
            _, _, client, err, warning = _parse_ai_request(
                {
                    "provider": "qwen",
                    "model": "qwen3-max",
                    "api_key": "sk-test",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                }
            )
            self.assertIsNone(err)
            self.assertIsNone(warning)
            self.assertFalse(client.web_search)


# ========== 辅助函数 ==========


class TestAttachWarning(unittest.TestCase):
    """_attach_warning：warning 非空时写入 payload 顶层"""

    def test_warning_attached(self):
        payload = {"success": True}
        result = _attach_warning(payload, "注意：xxx")
        self.assertEqual(result["_warning"], "注意：xxx")

    def test_no_warning_no_key(self):
        payload = {"success": True}
        result = _attach_warning(payload, None)
        self.assertNotIn("_warning", result)
        result = _attach_warning(payload, "")
        self.assertNotIn("_warning", result)


class TestSafeClose(unittest.TestCase):
    """_safe_close：安全关闭适配器，不抛异常"""

    def test_none_adapter(self):
        _safe_close(None)  # 不应抛异常

    def test_closed_adapter(self):
        class _Closed:
            def close(self):
                raise RuntimeError("already closed")

        _safe_close(_Closed())  # 不应抛异常

    def test_normal_adapter(self):
        closed = []

        class _Ok:
            def close(self):
                closed.append(True)

        _safe_close(_Ok())
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main(verbosity=2)
