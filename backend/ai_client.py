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
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 获取 base_url
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif provider in MODEL_PRESETS:
            self.base_url = MODEL_PRESETS[provider]["base_url"].rstrip("/")
        else:
            self.base_url = "https://api.openai.com/v1"

        # 百度千帆已支持 OpenAI 兼容接口，无需特殊处理
        self._is_ernie = False

    def _build_messages(self, data_summary: Dict[str, Any], question: Optional[str] = None) -> List[Dict[str, str]]:
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

        # 构建数据摘要
        summary_text = "## 数据库统计信息\n\n"
        summary_text += f"- 总记录数：{data_summary.get('total_rows', 0)}\n"
        summary_text += f"- 字段数：{data_summary.get('total_columns', 0)}\n"
        summary_text += f"- 审核状态：{data_summary.get('audit_stats', {})}\n\n"

        # 字段统计
        field_stats = data_summary.get("field_stats", [])
        if field_stats:
            summary_text += "### 各字段统计\n\n"
            for fs in field_stats:
                summary_text += f"**{fs.get('label', fs.get('key', ''))}**：\n"
                for k, v in fs.get("stats", {}).items():
                    summary_text += f"- {k}：{v}\n"
                summary_text += "\n"

        # 最近日志
        recent_logs = data_summary.get("recent_logs", [])
        if recent_logs:
            summary_text += "### 最近操作日志（最后 20 条）\n\n"
            for log in recent_logs[:20]:
                summary_text += (
                    f"- [{log.get('timestamp', '')}] "
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
    ) -> Dict[str, Any]:
        """
        分析数据并返回报告。

        Args:
            data_summary: 数据统计摘要
            question: 用户自定义问题（可选）
            stream: 是否使用流式响应

        Returns:
            dict: {"success": True, "content": "...", "tokens": ...}
                  或 {"success": False, "error": "..."}
        """
        messages = self._build_messages(data_summary, question)

        try:
            return self._call_openai_compatible(messages, stream)
        except requests.exceptions.Timeout:
            return {"success": False, "error": "请求超时，请检查网络或稍后重试"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接到 API 服务器，请检查 Base URL 和网络"}
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    detail = e.response.json()
                    # 优先提取 OpenAI/DashScope/DeepSeek 等返回的 message
                    if isinstance(detail, dict):
                        provider_msg = detail.get('error', {}).get('message') if isinstance(detail.get('error'), dict) else None
                        if provider_msg:
                            error_msg = f"HTTP {e.response.status_code}: {provider_msg}"
                        elif detail.get('message'):
                            error_msg = f"HTTP {e.response.status_code}: {detail['message']}"
                        else:
                            error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                    else:
                        error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                except Exception:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            return {"success": False, "error": f"AI 分析失败：{error_msg}"}

    def _call_openai_compatible(self, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        """调用 OpenAI 兼容 API"""
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

        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

        if stream:
            # 流式响应：收集所有 chunks
            content_parts = []
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            content_parts.append(delta["content"])
                    except json.JSONDecodeError:
                        continue
            content = "".join(content_parts)
        else:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

        # 估算 token 用量
        usage = data.get("usage", {}) if not stream else {}

        return {
            "success": True,
            "content": content,
            "tokens": {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
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

        try:
            return self._call_openai_compatible(messages)
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    detail = e.response.json()
                    if isinstance(detail, dict):
                        provider_msg = detail.get('error', {}).get('message') if isinstance(detail.get('error'), dict) else None
                        if provider_msg:
                            error_msg = f"HTTP {e.response.status_code}: {provider_msg}"
                        elif detail.get('message'):
                            error_msg = f"HTTP {e.response.status_code}: {detail['message']}"
                        else:
                            error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                    else:
                        error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                except Exception:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            return {"success": False, "error": f"对话失败：{error_msg}"}

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
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    detail = e.response.json()
                    if isinstance(detail, dict):
                        provider_msg = detail.get('error', {}).get('message') if isinstance(detail.get('error'), dict) else None
                        if provider_msg:
                            error_msg = f"HTTP {e.response.status_code}: {provider_msg}"
                        elif detail.get('message'):
                            error_msg = f"HTTP {e.response.status_code}: {detail['message']}"
                        else:
                            error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                    else:
                        error_msg = f"HTTP {e.response.status_code}: {json.dumps(detail, ensure_ascii=False)}"
                except Exception:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
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
    )
