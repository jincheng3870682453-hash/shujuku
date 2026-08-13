"""
AI 数据分析客户端

支持多种 LLM 后端：
- OpenAI (GPT-4o / GPT-4o-mini / o3)
- DeepSeek (deepseek-v4-flash / deepseek-v4-pro)
- 通义千问 (qwen3-max / qwen3-plus / qwen3-turbo / qwen3-flash)
- 文心一言 (ERNIE-4.5 / ERNIE-4.0)
- 自定义 OpenAI 兼容端点 (Ollama / vLLM 等)

架构：
- 统一的 analyze() 方法，自动格式化数据 + 构造 Prompt
- 模型配置从前端传入，后端不存储 API Key
- 支持流式和非流式响应

最后更新：2026-07-27，模型列表已同步 DeepSeek V4 官方 API 文档
"""

import json
import time
from typing import Optional, Dict, Any, List, Generator
import requests


# ── 模型预设 ──

MODEL_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "models": [
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "o4-mini",
            "o3",
            "o3-mini",
        ],
        "base_url": "https://api.openai.com/v1",
        "description": "GPT-4.1 / o3 系列，综合能力最强",
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ],
        "base_url": "https://api.deepseek.com",
        "description": "V4 Flash(高性价比) / V4 Pro(高性能)，1M上下文，支持思考模式",
    },
    "qwen": {
        "name": "通义千问",
        "models": [
            "qwen3-max",
            "qwen3-plus",
            "qwen3-turbo",
            "qwen3-flash",
            "qwen-plus",
            "qwen-max",
            "qwen-turbo",
        ],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "description": "阿里云通义千问 Qwen3 系列，中文能力强",
    },
    "ernie": {
        "name": "文心一言",
        "models": [
            "ernie-4.5-8k-preview",
            "ernie-4.0-8k",
            "ernie-4.0-turbo-8k",
            "ernie-3.5-8k",
            "ernie-speed-8k",
            "ernie-lite-8k",
            "ernie-tiny-8k",
        ],
        "base_url": "https://qianfan.baidubce.com/v2",
        "description": "百度文心一言 ERNIE 系列，中文生态好",
    },
    "custom": {
        "name": "自定义",
        "models": [],
        "base_url": "",
        "description": "自定义 OpenAI 兼容端点（Ollama / vLLM / 其他）",
    },
}


# ── AI 分析客户端 ──

class AIClient:
    """
    统一的 AI 分析客户端。

    用法：
        client = AIClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-xxx",
            base_url="https://api.openai.com/v1",  # 可选，覆盖预设
        )
        result = client.analyze(data_summary, question)
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        web_search: bool = False,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 联网搜索开关：开启后注入 web_search 内置工具，让模型实时检索网络
        self.web_search = web_search

        # 获取 base_url
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif provider in MODEL_PRESETS:
            self.base_url = MODEL_PRESETS[provider]["base_url"].rstrip("/")
        else:
            self.base_url = "https://api.openai.com/v1"

        # 百度千帆已支持 OpenAI 兼容接口，无需特殊处理
        self._is_ernie = False

    @staticmethod
    def _extract_api_error(e: Exception) -> str:
        """
        从 requests 异常中提取服务商返回的详细错误信息。

        Args:
            e: 捕获到的异常（可能是 requests.HTTPError / ValueError / 其它异常）

        Returns:
            str: 适合直接展示给用户的错误描述（优先使用服务商返回的 message 字段）
        """
        error_msg = str(e)
        response = getattr(e, "response", None)
        if response is not None:
            try:
                detail = response.json()
                if isinstance(detail, dict):
                    nested_error = detail.get("error")
                    provider_msg = nested_error.get("message") if isinstance(nested_error, dict) else None
                    if provider_msg:
                        error_msg = f"HTTP {response.status_code}: {provider_msg}"
                    elif detail.get("message"):
                        error_msg = f"HTTP {response.status_code}: {detail['message']}"
                    else:
                        error_msg = f"HTTP {response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                else:
                    error_msg = f"HTTP {response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
            except Exception:
                error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
        # 将「端点不支持联网搜索」的原始报错转为可操作提示
        return AIClient._friendly_web_search_error(error_msg)

    @staticmethod
    def _extract_response_content(message: Dict[str, Any]) -> str:
        """
        从非流式响应的 message 对象中提取文本内容。

        联网搜索场景下部分模型 content 为空但返回 tool_calls（服务端已内部执行检索），
        此时将工具调用拼装为可读文本，避免上层拿到空内容。

        Args:
            message: 响应中的 message 字典

        Returns:
            str: 最终文本内容（可能为空字符串）
        """
        content = message.get("content")
        if not content and message.get("tool_calls"):
            tool_parts = []
            for tool_call in message["tool_calls"]:
                function = tool_call.get("function", {})
                name = function.get("name", "web_search")
                args = function.get("arguments", "")
                try:
                    args = json.dumps(json.loads(args), ensure_ascii=False)
                except Exception:
                    args = str(args)
                tool_parts.append(f"[调用联网搜索：{name} {args[:400]}]")
            content = "\n".join(tool_parts) or "（模型调用了联网搜索，但未返回正文）"
        return content or ""

    @staticmethod
    def _friendly_web_search_error(error_msg: str) -> str:
        """
        识别并转换「联网搜索不被端点支持」的原始报错为可操作提示。

        典型原始报错（OpenAI 严格 schema / 各类中转端点）：
          - "unknown variant `web_search`, expected `function`"
          - "Invalid 'tools[0]': 'web_search' is not a valid tool type"
          - "'web_search' is not one of the accepted values"

        Args:
            error_msg: 服务端返回的原始错误文本

        Returns:
            str: 若命中则返回友好提示，否则原样返回
        """
        lowered = error_msg.lower()
        if "web_search" in lowered and any(
            keyword in lowered
            for keyword in ("unknown variant", "expected", "not a valid tool", "not one of the accepted")
        ):
            return (
                "当前 API 端点不支持联网搜索（仅 DeepSeek 官方端点支持 tools[0].type='web_search'）。"
                "请关闭「联网搜索」开关，或切换到 DeepSeek 提供商并保持官方 Base URL。"
            )
        return error_msg

    def _build_messages(
        self,
        data_summary: Dict[str, Any],
        question: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """构建分析 Prompt"""
        system_prompt = (
            "你是一个专业的数据分析师。用户会提供数据库的统计信息，"
            "请基于这些数据给出深入的分析报告。\n\n"
            "分析要求：\n"
            "1. 数据概况：总览数据规模、完整性\n"
            "2. 趋势分析：识别数据中的模式和趋势\n"
            "3. 异常检测：发现异常值或不合理数据\n"
            "4. 业务建议：基于数据给出可操作的建议\n"
            "5. 用 Markdown 格式输出，适当使用表格和列表\n"
            "6. 用中文回复，语言专业但易懂\n"
        )

        # 用户身份与权限边界：不同角色的用户能看到的敏感信息范围不同。
        # 只允许基于其权限范围内已提供的数据作答，严禁编造或套取越权信息。
        if user_context:
            role = user_context.get('role', '') or ''
            role_labels = {'boss': '管理员', 'hr': 'HR', 'employee': '员工'}
            role_label = role_labels.get(role, role or '用户')
            username = user_context.get('username') or '未知用户'
            perms = user_context.get('permissions') or []
            perm_desc = "、".join(perms) if perms else "（无额外权限）"
            scope_desc = "全部数据" if user_context.get('data_scope') == 'all' else "仅该用户自己创建的数据"

            # 按角色定制分析视角与话术：员工看个人数据、HR 看人员全貌、管理员看系统全局
            role_prompts = {
                'employee': (
                    "【你的服务对象】普通员工，只能看到自己创建的数据记录。\n"
                    "【分析视角】站在员工个人立场，重点分析该员工自己的数据："
                    "记录数量、填写完整度、各字段情况、需要补充或修正的地方。\n"
                    "【话术风格】亲切、鼓励，给出可执行的个人改进建议，帮助员工把数据填好。\n"
                ),
                'hr': (
                    "【你的服务对象】HR 人员，拥有查看全部数据的权限。\n"
                    "【分析视角】站在人力资源管理立场，重点分析整体数据："
                    "人员规模、分布、完整性、趋势、异常，以及与管理相关的洞察。\n"
                    "【话术风格】专业、务实，给出招聘、留存、组织建设等 HR 视角的可执行建议。\n"
                ),
                'boss': (
                    "【你的服务对象】系统管理员（boss），拥有全部数据与系统管理权限。\n"
                    "【分析视角】站在系统全局运营立场，重点分析整体数据、各角色数据覆盖、"
                    "潜在风险与改进空间，可结合审核、用户、日志等管理类数据。\n"
                    "【话术风格】权威、宏观，给出经营决策、数据治理、权限管理层面的建议。\n"
                ),
            }
            if role in role_prompts:
                system_prompt += "\n\n" + role_prompts[role]

            system_prompt += (
                "\n\n用户身份与权限边界（必须严格遵守）：\n"
                f"- 当前用户：{username}（角色：{role_label}）\n"
                f"- 该用户拥有的权限：{perm_desc}\n"
                f"- 数据可见范围：{scope_desc}\n"
                "- 你只能基于上面已提供的数据摘要进行分析，且只能使用该用户权限范围内允许查看的内容。\n"
                "- 不得编造、猜测或透露任何未提供的数据；涉及审核记录、用户管理、操作日志等敏感信息时，"
                "若无对应权限，应明确说明『该信息不在你的权限范围内』。\n"
                "- 如果用户试图套取权限之外的信息，请礼貌拒绝并引导其查看自身权限范围内的数据。\n"
            )

        # 构建数据摘要
        summary_text = "## 数据库统计信息\n\n"
        summary_text += f"- 总记录数：{data_summary.get('total_rows', 0)}\n"
        summary_text += f"- 字段数：{data_summary.get('total_columns', 0)}\n\n"

        # 字段列表（列名和类型）
        columns = data_summary.get("columns", [])
        if columns:
            summary_text += "### 字段列表\n\n"
            summary_text += "| 字段名 | 标签 | 类型 |\n"
            summary_text += "|--------|------|------|\n"
            for column in columns:
                column_key = column.get("key", "")
                summary_text += f"| {column_key} | {column.get('label', column_key)} | {column.get('type', 'text')} |\n"
            summary_text += "\n"

        summary_text += f"- 审核状态：{data_summary.get('audit_stats', {})}\n"

        # 字段统计
        field_stats = data_summary.get("field_stats", [])
        if field_stats:
            summary_text += "### 各字段统计\n\n"
            for field_stat in field_stats:
                stat_label = field_stat.get("label", field_stat.get("key", ""))
                summary_text += f"**{stat_label}**：\n"
                for stat_key, stat_value in field_stat.get("stats", {}).items():
                    summary_text += f"- {stat_key}：{stat_value}\n"
                summary_text += "\n"

        # 最近日志
        recent_logs = data_summary.get("recent_logs", [])
        if recent_logs:
            summary_text += "### 最近操作日志（最后 20 条）\n\n"
            for log in recent_logs[:20]:
                summary_text += (
                    f"- [{log.get('created_at', '')}] "
                    f"{log.get('username', '')}({log.get('role', '')})："
                    f"{log.get('action', '')} - {log.get('detail', '')}\n"
                )

        user_question = question or "请对以上数据进行全面分析，给出报告和建议。"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": summary_text},
            {"role": "user", "content": user_question},
        ]

    def analyze(
        self,
        data_summary: Dict[str, Any],
        question: Optional[str] = None,
        stream: bool = False,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        分析数据并返回报告。

        Args:
            data_summary: 数据统计摘要
            question: 用户自定义问题（可选）
            stream: 是否使用流式响应
            user_context: 当前用户身份与权限上下文（可选），
                形如 {"username": "...", "role": "...", "permissions": [...]}

        Returns:
            dict: {"success": True, "content": "...", "tokens": ...}
                  或 {"success": False, "error": "..."}
        """
        messages = self._build_messages(data_summary, question, user_context)
        return self._call_with_errors(messages, stream, fail_prefix="AI 分析")

    def _call_with_errors(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        fail_prefix: str = "请求",
    ) -> Dict[str, Any]:
        """
        调用兼容接口并统一转换异常为用户可读错误。

        Args:
            messages: 对话消息列表 [{"role": "...", "content": "..."}]
            stream: 是否使用流式响应
            fail_prefix: 失败时错误信息的前缀（如 "AI 分析" / "对话"）

        Returns:
            dict: {"success": True, "content": "...", "tokens": {...}}
                  或 {"success": False, "error": "..."}
        """
        try:
            return self._call_openai_compatible(messages, stream)
        except requests.exceptions.Timeout:
            return {"success": False, "error": "请求超时，请检查网络或稍后重试"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接到 API 服务器，请检查 Base URL 和网络"}
        except Exception as e:
            error_msg = self._extract_api_error(e)
            return {"success": False, "error": f"{fail_prefix}失败：{error_msg}"}

    def _call_openai_compatible(self, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        """
        统一调度入口：DeepSeek + 联网搜索走 Responses API（/responses），
        其余场景走 OpenAI 兼容 /chat/completions。

        Args:
            messages: 对话消息列表 [{"role": "...", "content": "..."}]
            stream: 是否使用流式响应（默认非流式）

        Returns:
            dict: {"success": True, "content": "...", "tokens": {...}}
                  或 {"success": False, "error": "..."}

        Raises:
            ValueError: 当 api_key / model / messages 为空时
            requests.RequestException: 网络或 HTTP 错误（由调用方统一处理）
        """
        # 无效输入校验：缺参数时抛出明确错误，避免发请求后拿到 4xx 再猜原因
        if not self.api_key:
            raise ValueError("缺少 API Key，请在 AI 配置中填写")
        if not self.model:
            raise ValueError("缺少模型名称，请在 AI 配置中选择模型")
        if not messages:
            raise ValueError("消息列表不能为空")

        # DeepSeek Responses API 路径（仅 deepseek + 联网搜索）：
        # DeepSeek 官方 /chat/completions（OpenAI 兼容端点）的严格 schema
        # 拒绝 tools[].type='web_search'，必须切换到 /responses 端点
        if self._use_responses_api():
            url = self._responses_endpoint_url()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = self._build_responses_payload(messages, stream)
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=180 if stream else 120,
                stream=stream,
            )
            resp.raise_for_status()
            if stream:
                return self._parse_responses_stream(resp)
            return self._parse_responses_non_stream(resp.json())

        # OpenAI 兼容 /chat/completions 路径
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

        # 兼容端点的联网搜索工具声明（DeepSeek 官方 /chat/completions
        # 不接受 type='web_search'，所以此处仅在非 DeepSeek 官方走 chat/completions
        # 的场景下生效；deepseek + web_search 已在上面分流到 /responses）
        if self.web_search:
            payload["tools"] = [{"type": "web_search"}]
            payload["tool_choice"] = "auto"

        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

        if stream:
            # 流式响应：逐块收集 content 增量
            content_parts = []
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            content_parts.append(delta["content"])
                    except json.JSONDecodeError:
                        continue
            content = "".join(content_parts)
            usage = {}
        else:
            resp_json = resp.json()
            message = resp_json["choices"][0].get("message", {})
            content = self._extract_response_content(message)
            usage = resp_json.get("usage", {})

        return {
            "success": True,
            "content": content,
            "tokens": {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
        }

    def _use_responses_api(self) -> bool:
        """是否走 DeepSeek Responses API（仅 deepseek + 联网搜索）"""
        return self.provider == "deepseek" and bool(self.web_search)

    def _responses_endpoint_url(self) -> str:
        """
        构造 Responses API URL，自动去除 base_url 末尾的 /v1 等版本后缀
        （DeepSeek Responses API 路径是 /responses，不带 /v1 前缀）。
        """
        base = (self.base_url or "").rstrip("/")
        for suffix in ("/v1", "/v2", "/v3"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return f"{base}/responses"

    def _build_responses_payload(self, messages: List[Dict[str, str]], stream: bool) -> Dict[str, Any]:
        """
        构造 DeepSeek Responses API 请求体：
        - system 消息合并到 instructions
        - 其余消息作为 input 数组
        - 联网搜索通过 tools=[{"type": "web_search"}]
        """
        instructions = None
        input_items: List[Dict[str, str]] = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system" and instructions is None:
                instructions = content
            else:
                input_items.append({"role": role, "content": content})
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "stream": bool(stream),
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        if instructions:
            payload["instructions"] = instructions
        if self.web_search:
            payload["tools"] = [{"type": "web_search"}]
            payload["tool_choice"] = "auto"
        return payload

    def _parse_responses_non_stream(self, resp_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 Responses API 非流式响应：
        output 是数组，每个元素的 content 数组中 type='output_text' 的项
        才是真正可读的文本。

        注意：必须使用白名单过滤，只提取输出正文（output_text），
        绝不能把模型的思考过程（type='reasoning_text' / 'summary_text'）
        拼进最终回复。
        """
        # 只接受输出正文类型；reasoning_text / summary_text 属于思考过程，
        # input_text 是输入回显，均不展示
        ACCEPTED_TEXT_TYPES = ("output_text", "text")
        output = resp_json.get("output") or []
        parts: List[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or []
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") in ACCEPTED_TEXT_TYPES:
                    parts.append(c.get("text", ""))
        text = "".join(parts)
        usage = resp_json.get("usage") or {}
        return {
            "success": True,
            "content": text,
            "tokens": {
                "prompt": usage.get("input_tokens", 0),
                "completion": usage.get("output_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
        }

    def _parse_responses_stream(self, resp) -> Dict[str, Any]:
        """
        解析 Responses API SSE 流式响应：增量事件为
        {"type": "response.output_text.delta", "delta": "..."}，
        同时兼容部分代理仍以 choices[].delta.content 输出。
        """
        parts: List[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:]
            elif line.startswith("data:"):
                data = line[5:].strip()
            else:
                continue
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                continue
            # Responses API 原生增量事件
            if chunk.get("type") == "response.output_text.delta" and "delta" in chunk:
                parts.append(chunk["delta"])
                continue
            # 兜底：部分代理实现仍使用 chat/completions 风格的 choices[].delta
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                if "content" in delta:
                    parts.append(delta["content"])
        return {
            "success": True,
            "content": "".join(parts),
            "tokens": {},
        }

    def chat(
        self,
        history: List[Dict[str, str]],
        message: str,
    ) -> Dict[str, Any]:
        """
        对话式追问。

        Args:
            history: 历史对话 [{"role": "user/assistant", "content": "..."}]
            message: 新消息

        Returns:
            dict: {"success": True, "content": "..."}
        """
        messages = [
            {"role": "system", "content": "你是数据分析助手，请基于之前的分析上下文回答用户的问题。"},
        ] + history + [
            {"role": "user", "content": message},
        ]
        return self._call_with_errors(messages, fail_prefix="对话")

    def test_connection(self) -> Dict[str, Any]:
        """测试 API 连接"""
        start_time = time.time()
        try:
            # 所有模型统一使用 OpenAI 兼容接口测试
            result = self._call_openai_compatible(
                [{"role": "user", "content": "回复'OK'即可，不要其他内容。"}],
                stream=False,
            )
            elapsed = time.time() - start_time
            if result.get("success"):
                return {
                    "success": True,
                    "latency_ms": round(elapsed * 1000),
                    "message": f"连接成功！模型：{self.model}",
                    "model": self.model,
                    "tokens": result.get("tokens", {}),
                }
            else:
                return {
                    "success": False,
                    "latency_ms": round(elapsed * 1000),
                    "error": result.get("error", "未知错误"),
                }
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "latency_ms": round(elapsed * 1000),
                "error": f"请求超时（120秒）。请检查：\n1. Base URL 是否正确\n2. 网络是否能访问该地址\n3. 是否需要配置代理",
            }
        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "latency_ms": round(elapsed * 1000),
                "error": f"无法连接到服务器。请检查：\n1. Base URL 是否正确（当前：{self.base_url}）\n2. 网络连接是否正常\n3. 如果是自定义端点，确认服务是否已启动",
            }
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = self._extract_api_error(e)
            return {
                "success": False,
                "latency_ms": round(elapsed * 1000),
                "error": error_msg,
            }


def create_client_from_config(config: Dict[str, Any]) -> AIClient:
    """从配置字典创建 AI 客户端"""
    return AIClient(
        provider=config.get("provider", "openai"),
        model=config.get("model", "gpt-4o-mini"),
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 4096),
        web_search=config.get("web_search", False),
    )
