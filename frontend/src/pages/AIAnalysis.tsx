/**
 * AI 数据分析页面
 *
 * 功能：
 * - 一键分析：自动汇总数据库信息，调用 AI 生成分析报告
 * - 对话追问：基于分析结果进行多轮对话
 * - 报告导出：导出 Markdown / 复制到剪贴板
 * - 多模型支持：OpenAI / DeepSeek / 通义千问 / 文心一言 / 自定义
 *
 * 安全设计：
 * - API Key 不会持久化存储在前端 localStorage
 * - 每次分析需要输入 Key（或从 session 读取）
 * - 前端仅展示结果，不缓存原始数据
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Card,
  Button,
  Select,
  Input,
  Typography,
  Space,
  Divider,
  message,
  Spin,
  Tag,
  Collapse,
  Tooltip,
  Empty,
  Alert,
  Modal,
  Switch,
} from "antd";
import {
  RobotOutlined,
  SendOutlined,
  ReloadOutlined,
  CopyOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MessageOutlined,
  FileTextOutlined,
  ApiOutlined,
  AudioOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import httpClient, { aiClient } from "../api/client";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ── 模型预设 ──
interface ModelPreset {
  name: string;
  models: string[];
  base_url: string;
  description: string;
}

// ── 对话消息 ──
interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

// ── AI 配置 ──
interface AIConfig {
  provider: string;
  model: string;
  api_key: string;
  base_url: string;
  temperature: number;
  web_search: boolean;
}

const DEFAULT_CONFIG: AIConfig = {
  provider: "openai",
  model: "gpt-4.1-mini",
  api_key: "",
  base_url: "",
  temperature: 0.7,
  web_search: false,
};

const AIAnalysis: React.FC = () => {
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── 状态 ──
  // API Key 仅保存在 React 内存中，不写入 sessionStorage（安全性）
  // provider、model、base_url 会持久化到 sessionStorage 方便下次使用
  const [config, setConfig] = useState<AIConfig>(() => {
    try {
      const saved = sessionStorage.getItem("ai_config");
      if (saved) {
        // 恢复除 api_key 以外的配置，api_key 每次都需要手动输入
        const parsed = JSON.parse(saved);
        return { ...DEFAULT_CONFIG, ...parsed, api_key: "" };
      }
    } catch {}
    return DEFAULT_CONFIG;
  });
  const [modelsPresets, setModelsPresets] = useState<Record<string, ModelPreset>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  // ── 报告和对话历史：按用户存储在后端，切换账号/设备不混淆 ──
  const [report, setReport] = useState<string>("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  const [chatInput, setChatInput] = useState("");
  const [chatting, setChatting] = useState(false);
  // ── 语音输入（Web Speech API，仅识别用户语音）──
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "success" | "error">("idle");
  const [dataSummary, setDataSummary] = useState<string>("");
  // ── 当前登录用户身份（影响 AI 分析视角与可见数据范围）──
  const [myRole, setMyRole] = useState<string>("");
  const [myRoleLabel, setMyRoleLabel] = useState<string>("");

  // ── 挂载时从后端加载当前用户的历史记录（按用户隔离）──
  useEffect(() => {
    let mounted = true;
    httpClient
      .get("/ai/history")
      .then((res: any) => {
        if (!mounted || !res?.success) return;
        setReport(res.report || "");
        setChatHistory(Array.isArray(res.chat_history) ? res.chat_history : []);
      })
      .catch(() => {
        // 加载失败静默处理，保持空白状态
      });
    return () => {
      mounted = false;
    };
  }, []);

  // ── 保存 report / chatHistory 到后端（按用户隔离，防抖）──
  const saveHistoryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (saveHistoryTimer.current) clearTimeout(saveHistoryTimer.current);
    saveHistoryTimer.current = setTimeout(() => {
      httpClient
        .post("/ai/history", { report, chat_history: chatHistory })
        .catch(() => {});
    }, 800);
    return () => {
      if (saveHistoryTimer.current) clearTimeout(saveHistoryTimer.current);
    };
  }, [report, chatHistory]);

  // ── 加载模型预设 ──
  useEffect(() => {
    httpClient
      .get("/ai/models")
      .then((res: any) => {
        if (res.success) {
          setModelsPresets(res.models);
        }
      })
      .catch(() => {
        // 使用默认预设（2026-07 更新版）
        setModelsPresets({
          openai: { name: "OpenAI", models: ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o4-mini", "o3", "o3-mini"], base_url: "https://api.openai.com/v1", description: "GPT-4.1 / o3 系列" },
          deepseek: { name: "DeepSeek", models: ["deepseek-v4-flash", "deepseek-v4-pro"], base_url: "https://api.deepseek.com", description: "V4 Flash(高性价比) / V4 Pro(高性能)" },
          qwen: { name: "通义千问", models: ["qwen3-max", "qwen3-plus", "qwen3-turbo", "qwen3-flash", "qwen-plus", "qwen-max", "qwen-turbo"], base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", description: "阿里云 Qwen3" },
          ernie: { name: "文心一言", models: ["ernie-4.5-8k-preview", "ernie-4.0-8k", "ernie-4.0-turbo-8k", "ernie-3.5-8k", "ernie-speed-8k", "ernie-lite-8k", "ernie-tiny-8k"], base_url: "https://qianfan.baidubce.com/v2", description: "百度千帆" },
          custom: { name: "自定义", models: [], base_url: "", description: "自定义 OpenAI 兼容端点" },
        });
      });
  }, []);

  // ── 获取当前登录用户身份（用于提示 AI 分析视角与数据范围）──
  useEffect(() => {
    httpClient
      .get("/me")
      .then((res: any) => {
        const role: string = res?.role || "";
        setMyRole(role);
        const labels: Record<string, string> = { boss: "管理员", hr: "HR", employee: "员工" };
        setMyRoleLabel(labels[role] || role || "普通用户");
      })
      .catch(() => {});
  }, []);

  // ── 自动滚动到底部 ──
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // ── 配置变更 ──
  const updateConfig = useCallback(
    (key: keyof AIConfig, value: string | number | boolean) => {
      setConfig((prev) => {
        const next = { ...prev, [key]: value };
        // 切换 provider 时自动选第一个模型
        if (key === "provider" && modelsPresets[value as string]) {
          next.model = modelsPresets[value as string].models[0];
          next.base_url = modelsPresets[value as string].base_url;
          // 联网搜索仅 DeepSeek 的 Responses API（/responses 端点）原生支持
          // tools[0].type='web_search'；后端会自动切到 /responses 端点。
          // 切到 DeepSeek 时默认开启，切到其他 provider 时强制关闭，
          // 避免请求被服务端以 400 拒绝。
          next.web_search = value === "deepseek";
        }
        // 保存到 sessionStorage（排除 api_key，防止明文泄露）
        const { api_key, ...safeConfig } = next;
        try {
          sessionStorage.setItem("ai_config", JSON.stringify(safeConfig));
        } catch {}
        return next;
      });
      setConnectionStatus("idle");
    },
    [modelsPresets]
  );

  // 当前 provider 是否支持联网搜索（仅 DeepSeek 原生支持）
  const webSearchSupported = config.provider === "deepseek";

  // 从请求异常中提取可读的错误消息文本（供消息提示、对话记录等场景复用）
  const extractErrorMessage = (error: any, fallback: string): string => {
    if (typeof error === "string") return error || fallback;
    const data = error?.response?.data;
    if (data?.error) return String(data.error);
    if (data?.message) return String(data.message);
    if (typeof data === "string") return data.slice(0, 200);
    if (error?.message) return error.message;
    return fallback;
  };

  // 展示后端返回的具体错误信息（优先从 error.response.data 里取完整错误）
  const showError = (error: any, fallback: string) => {
    // 错误响应中若附带兼容性提示（如联网搜索被自动关闭），同样先展示
    if (error?.response?.data?._warning) {
      message.warning(error.response.data._warning);
    }
    let msg = fallback;
    let detail = "";
    if (typeof error === "string") {
      msg = error || fallback;
    } else if (error?.response?.data?.error) {
      msg = String(error.response.data.error);
      detail = JSON.stringify(error.response.data, null, 2);
    } else if (error?.response?.data?.message) {
      msg = String(error.response.data.message);
      detail = JSON.stringify(error.response.data, null, 2);
    } else if (typeof error?.response?.data === "string") {
      detail = error.response.data;
      // 如果是 HTML 错误页，提取关键文本
      if (detail.trim().startsWith("<!doctype") || detail.trim().startsWith("<html")) {
        const titleMatch = detail.match(/<title>(.*?)<\/title>/i);
        const h1Match = detail.match(/<h1>(.*?)<\/h1>/i);
        const pMatch = detail.match(/<p>(.*?)<\/p>/i);
        msg = titleMatch?.[1] || h1Match?.[1] || fallback;
        detail = `${fallback}，服务器返回：\n${titleMatch?.[1] || ""}\n${h1Match?.[1] || ""}\n${pMatch?.[1] || ""}\n\n原始响应（HTML）：\n${detail.slice(0, 1200)}`;
      } else {
        msg = detail.slice(0, 200);
      }
    } else if (error?.response?.data) {
      detail = JSON.stringify(error.response.data, null, 2);
    } else if (error?.message) {
      msg = `${fallback}：${error.message}`;
    }
    if (detail && detail !== msg) {
      message.error(msg || fallback);
      Modal.error({
        title: fallback,
        content: (
          <pre
            style={{
              maxHeight: 300,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              fontSize: 12,
              background: "#f5f5f5",
              padding: 12,
              borderRadius: 4,
              marginTop: 8,
            }}
          >
            {detail}
          </pre>
        ),
        okText: "知道了",
      });
    } else {
      message.error(msg || fallback);
    }
  };

  // 展示后端返回的兼容性提示（如联网搜索被自动关闭）
  const showWarning = (res: any) => {
    if (res?._warning) {
      message.warning(res._warning);
    }
  };

  // ── 测试连接 ──
  // 用当前 AI 配置发起一次最小请求，验证 API Key / Base URL 是否可用，
  // 成功则展示模型名与延迟，失败则提示具体原因。
  const testConnection = async () => {
    if (!config.api_key) {
      message.warning("请先填写 API Key");
      return;
    }
    setTesting(true);
    setConnectionStatus("idle");
    try {
      const res: any = await aiClient.post("/ai/test", config);
      showWarning(res);
      if (res.success) {
        setConnectionStatus("success");
        message.success(`${res.message} (${res.latency_ms}ms)`);
      } else {
        setConnectionStatus("error");
        message.error(res.error || "连接失败");
      }
    } catch (e: any) {
      setConnectionStatus("error");
      showError(e, "连接失败");
    } finally {
      setTesting(false);
    }
  };

  // ── 一键分析 ──
  // 汇总当前数据库统计信息发送给 AI 生成分析报告；
  // customQuestion 可选，传入后作为用户自定义问题代替默认分析要求。
  const startAnalysis = async (customQuestion?: string) => {
    if (!config.api_key) {
      message.warning("请先填写 API Key");
      setShowConfig(true);
      return;
    }
    setLoading(true);
    // 注意：不要在分析开始前清空 report/chatHistory，否则切换页面会丢失旧结果
    setDataSummary("");
    try {
      const res: any = await aiClient.post("/ai/analyze", {
        ...config,
        question: customQuestion || "",
      });
      showWarning(res);
      if (res.success) {
        setReport(res.content);
        setChatHistory([]); // 新分析开始，清空旧对话（后端记录会随防抖保存更新）
        // 保存数据摘要用于对话上下文
        setDataSummary("已分析数据库，可继续追问。");
        message.success(`分析完成${res.tokens ? ` (${res.tokens.total} tokens)` : ""}`);
      } else {
        message.error(res.error || "分析失败");
      }
    } catch (e: any) {
      showError(e, "分析失败，请检查配置");
    } finally {
      setLoading(false);
    }
  };

  // ── 对话追问 ──
  // 将输入框消息追加到历史后发给 AI 继续对话，返回内容以气泡形式追加到聊天列表。
  const sendChat = async () => {
    if (!chatInput.trim() || !config.api_key) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatHistory((prev) => [...prev, { role: "user", content: userMsg }]);
    setChatting(true);
    try {
      const res: any = await aiClient.post("/ai/chat", {
        ...config,
        history: chatHistory,
        message: userMsg,
      });
      showWarning(res);
      if (res.success) {
        setChatHistory((prev) => [...prev, { role: "assistant", content: res.content }]);
      } else {
        setChatHistory((prev) => [...prev, { role: "assistant", content: `❌ 错误：${res.error}` }]);
      }
    } catch (e: any) {
      const errText = extractErrorMessage(e, "未知错误");
      setChatHistory((prev) => [...prev, { role: "assistant", content: `❌ 请求失败：${errText}` }]);
    } finally {
      setChatting(false);
    }
  };

  // ── 语音识别：识别用户语音填入追问框 ──
  // 只识别用户说的话（中/英文）；一旦 1.5 秒未识别到有效语音立即自动暂停。
  // 组件卸载时清理计时器与识别实例，避免内存泄漏。
  useEffect(() => {
    return () => {
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
      try {
        recognitionRef.current?.stop();
      } catch {}
    };
  }, []);

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  const startSilenceTimer = () => {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      // 1.5 秒未识别到有效中文/英文语音 → 自动暂停识别
      try {
        recognitionRef.current?.stop();
      } catch {}
    }, 1500);
  };

  const stopVoiceInput = () => {
    clearSilenceTimer();
    try {
      recognitionRef.current?.stop();
    } catch {}
    setIsListening(false);
  };

  const startVoiceInput = () => {
    if (isListening) {
      // 再次点击 = 手动停止
      stopVoiceInput();
      return;
    }
    const SR: any =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      message.warning("当前环境不支持语音识别，请使用 Edge 或 Chrome 浏览器");
      return;
    }
    try {
      const rec = new SR();
      recognitionRef.current = rec;
      rec.lang = "zh-CN"; // 中英文语音识别（zh-CN 可识别常见英文单词）
      rec.continuous = true; // 持续识别，直到检测到静音
      rec.interimResults = true; // 实时返回中间结果，提升交互体验
      rec.maxAlternatives = 1;
      rec.onstart = () => {
        setIsListening(true);
        // 启动后立即计时：若用户始终不说话则 1.5s 后自动暂停
        startSilenceTimer();
      };
      rec.onresult = (event: any) => {
        let finalText = "";
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) finalText += result[0].transcript;
          else interimText += result[0].transcript;
        }
        setChatInput(finalText + interimText);
        // 每次识别到有效语音，重置 1.5s 静音计时器
        startSilenceTimer();
      };
      rec.onerror = (event: any) => {
        // no-speech/aborted 属于静音超时或手动停止，属正常情况，不提示
        if (event.error && event.error !== "no-speech" && event.error !== "aborted") {
          message.error(`语音识别失败：${event.error}`);
        }
        clearSilenceTimer();
        setIsListening(false);
      };
      rec.onend = () => {
        clearSilenceTimer();
        setIsListening(false);
        recognitionRef.current = null;
      };
      rec.start();
    } catch {
      message.error("无法启动语音识别，请检查麦克风权限");
      setIsListening(false);
    }
  };

  // ── 复制报告 ──
  const copyReport = () => {
    if (!report) return;
    navigator.clipboard.writeText(report).then(() => {
      message.success("报告已复制到剪贴板");
    });
  };

  // ── 导出报告 ──
  const exportReport = () => {
    if (!report) return;
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `数据分析报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    message.success("报告已下载");
  };

  // ── 当前 provider 的模型列表 ──
  const currentModels = modelsPresets[config.provider]?.models || [];
  // 是否显示自定义模型输入（所有 provider 都支持）
  const [customModelInput, setCustomModelInput] = useState("");

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 8px" }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 20 }}>
        <Title level={3} style={{ margin: 0 }}>
          <RobotOutlined style={{ marginRight: 8, color: "var(--accent-default, #1677ff)" }} />
          AI 数据分析
        </Title>
        <Text type="secondary">基于大语言模型自动分析数据库内容，生成报告并支持对话追问</Text>
      </div>

      {/* 配置区 */}
      <Collapse
        activeKey={showConfig ? ["config"] : []}
        onChange={(keys) => setShowConfig(keys.includes("config"))}
        style={{ marginBottom: 16 }}
        items={[
          {
            key: "config",
            label: (
              <Space>
                <SettingOutlined />
                <span>模型配置</span>
                {connectionStatus === "success" && (
                  <Tag color="success" icon={<CheckCircleOutlined />}>
                    已连接
                  </Tag>
                )}
                {connectionStatus === "error" && (
                  <Tag color="error" icon={<CloseCircleOutlined />}>
                    连接失败
                  </Tag>
                )}
              </Space>
            ),
            children: (
              <div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                    gap: 12,
                  }}
                >
                  {/* Provider 选择 */}
                  <div>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      AI 服务商
                    </Text>
                    <Select
                      value={config.provider}
                      onChange={(v) => updateConfig("provider", v)}
                      style={{ width: "100%" }}
                      options={Object.entries(modelsPresets).map(([key, p]) => ({
                        value: key,
                        label: (
                          <Space>
                            <span>{p.name}</span>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {p.description}
                            </Text>
                          </Space>
                        ),
                      }))}
                    />
                  </div>

                  {/* Model 选择 */}
                  <div>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      模型
                      <Tooltip title="可从下拉列表选择，也可直接输入自定义模型名">
                        <QuestionCircleOutlined style={{ marginLeft: 4, fontSize: 12, color: "#999" }} />
                      </Tooltip>
                    </Text>
                    <Select
                      value={config.model}
                      onChange={(v) => updateConfig("model", v)}
                      style={{ width: "100%" }}
                      showSearch
                      placeholder="选择或输入模型名"
                      mode={undefined}
                      options={currentModels.map((m) => ({ value: m, label: m }))}
                      dropdownRender={(menu) => (
                        <>
                          {menu}
                          <Divider style={{ margin: "8px 0" }} />
                          <div style={{ padding: "0 8px 4px" }}>
                            <Input
                              placeholder="输入自定义模型名后按回车"
                              value={customModelInput}
                              onChange={(e) => setCustomModelInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && customModelInput.trim()) {
                                  updateConfig("model", customModelInput.trim());
                                  setCustomModelInput("");
                                }
                                e.stopPropagation();
                              }}
                              onBlur={() => {
                                if (customModelInput.trim()) {
                                  updateConfig("model", customModelInput.trim());
                                  setCustomModelInput("");
                                }
                              }}
                              size="small"
                              suffix={
                                <Button
                                  type="link"
                                  size="small"
                                  style={{ padding: 0, fontSize: 11 }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (customModelInput.trim()) {
                                      updateConfig("model", customModelInput.trim());
                                      setCustomModelInput("");
                                    }
                                  }}
                                >
                                  确定
                                </Button>
                              }
                            />
                          </div>
                        </>
                      )}
                    />
                  </div>

                  {/* API Key */}
                  <div>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      API Key
                    </Text>
                    <Input.Password
                      value={config.api_key}
                      onChange={(e) => updateConfig("api_key", e.target.value)}
                      placeholder="sk-xxx 或您的 API Key"
                      autoComplete="new-password"
                      visibilityToggle={false}
                    />
                  </div>

                  {/* Base URL */}
                  <div>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      <Tooltip title="可选，默认使用服务商官方地址。Ollama 用户填 http://localhost:11434/v1">
                        Base URL <QuestionCircleOutlined />
                      </Tooltip>
                    </Text>
                    <Input
                      value={config.base_url}
                      onChange={(e) => updateConfig("base_url", e.target.value)}
                      placeholder={modelsPresets[config.provider]?.base_url || "自动填充"}
                    />
                  </div>

                  {/* 联网搜索 */}
                  <div>
                    <Text strong style={{ display: "block", marginBottom: 4 }}>
                      <Tooltip
                        title={
                          webSearchSupported
                            ? "开启后 DeepSeek 模型可实时检索网络获取最新信息"
                            : "联网搜索仅 DeepSeek 提供商支持，请先切换到 DeepSeek"
                        }
                      >
                        联网搜索 <QuestionCircleOutlined />
                      </Tooltip>
                    </Text>
                    <Switch
                      checked={config.web_search}
                      disabled={!webSearchSupported}
                      onChange={(v) => updateConfig("web_search", v)}
                      checkedChildren="开启"
                      unCheckedChildren="关闭"
                    />
                    <Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 4 }}>
                      {webSearchSupported ? "让 AI 实时检索网络" : "当前 provider 不支持联网搜索"}
                    </Text>
                  </div>
                </div>

                <Divider style={{ margin: "12px 0" }} />

                <Space>
                  <Button
                    type="primary"
                    icon={<ApiOutlined />}
                    onClick={testConnection}
                    loading={testing}
                    ghost
                  >
                    测试连接
                  </Button>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    API Key 仅保存在内存中，刷新页面后需重新输入
                  </Text>
                </Space>
              </div>
            ),
          },
        ]}
      />

      {/* 操作区 */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              onClick={() => startAnalysis()}
              loading={loading}
              disabled={!config.api_key}
            >
              一键分析
            </Button>
            <Button
              size="large"
              icon={<QuestionCircleOutlined />}
              onClick={() => {
                const q = prompt("输入你想让 AI 重点关注的问题：");
                if (q) startAnalysis(q);
              }}
              loading={loading}
              disabled={!config.api_key}
            >
              带问题分析
            </Button>
            {report && (
              <>
                <Button icon={<CopyOutlined />} onClick={copyReport}>
                  复制报告
                </Button>
                <Button icon={<FileTextOutlined />} onClick={exportReport}>
                  导出 Markdown
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    setReport("");
                    setChatHistory([]);
                    // 同步清除后端记录（按用户隔离）
                    httpClient.delete("/ai/history").catch(() => {});
                    message.success("已清除分析结果");
                  }}
                  danger
                >
                  清除分析
                </Button>
              </>
            )}
          </div>

          {myRole && (
            <Alert
              message={
                <Space wrap size={4}>
                  <Text strong style={{ fontSize: 13 }}>
                    <RobotOutlined /> 当前身份：{myRoleLabel}
                  </Text>
                  <Tag color={myRole === "boss" ? "gold" : myRole === "hr" ? "blue" : "green"}>
                    {myRole === "employee" ? "仅分析你创建的数据" : myRole === "hr" ? "可分析全部数据（HR 视角）" : "可分析全部数据（全局视角）"}
                  </Tag>
                </Space>
              }
              description={
                myRole === "employee"
                  ? "AI 仅会基于你创建的数据进行分析，不会涉及其他用户的数据。"
                  : "AI 会基于全部数据进行分析，并针对你的身份采用对应的分析视角。"
              }
              type={myRole === "employee" ? "success" : "warning"}
              showIcon
              style={{ fontSize: 13 }}
            />
          )}
          <Alert
            message={
              <span>
                支持 <Tag>OpenAI</Tag> <Tag>DeepSeek</Tag> <Tag>通义千问</Tag> <Tag>文心一言</Tag>{" "}
                <Tag>Ollama</Tag> <Tag>自定义端点</Tag>
              </span>
            }
            type="info"
            showIcon
            style={{ fontSize: 13 }}
          />
        </Space>
      </Card>

      {/* 分析报告 */}
      {loading && (
        <Card>
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <Spin
              indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
              tip="AI 正在分析数据..."
            />
            <br />
            <Text type="secondary" style={{ marginTop: 12, display: "block" }}>
              正在汇总数据库信息并调用 AI 分析，请稍候...
            </Text>
          </div>
        </Card>
      )}

      {!loading && !report && (
        <Card>
          <Empty
            image={<RobotOutlined style={{ fontSize: 64, color: "#d9d9d9" }} />}
            description={
              <span>
                点击「一键分析」让 AI 帮你分析数据库中的数据
                <br />
                <Text type="secondary">支持 5 种主流大模型，API Key 仅保存在当前会话</Text>
              </span>
            }
          />
        </Card>
      )}

      {report && (
        <>
          {/* 报告卡片 */}
          <Card
            title={
              <Space>
                <RobotOutlined style={{ color: "var(--accent-default, #1677ff)" }} />
                <span>AI 分析报告</span>
              </Space>
            }
            extra={
              <Space>
                <Button size="small" icon={<ReloadOutlined />} onClick={() => startAnalysis()}>
                  重新生成
                </Button>
                <Button size="small" icon={<CopyOutlined />} onClick={copyReport}>
                  复制
                </Button>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <div
              className="ai-report-content"
              style={{
                maxHeight: "60vh",
                overflowY: "auto",
                padding: "8px 0",
              }}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeStr = String(children).replace(/\n$/, "");
                    if (match) {
                      return (
                        <SyntaxHighlighter
                          style={oneLight}
                          language={match[1]}
                          PreTag="div"
                        >
                          {codeStr}
                        </SyntaxHighlighter>
                      );
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  table({ children }: any) {
                    return (
                      <div style={{ overflowX: "auto" }}>
                        <table>{children}</table>
                      </div>
                    );
                  },
                }}
              >
                {report}
              </ReactMarkdown>
            </div>
          </Card>

          {/* 对话追问 */}
          <Card
            title={
              <Space>
                <MessageOutlined />
                <span>对话追问</span>
                {chatting && <Tag color="processing">思考中...</Tag>}
              </Space>
            }
          >
            <div
              style={{
                maxHeight: 400,
                overflowY: "auto",
                marginBottom: 12,
                padding: "8px 0",
              }}
            >
              {chatHistory.length === 0 ? (
                <Text type="secondary">在下方输入问题，基于分析结果继续追问</Text>
              ) : (
                chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    style={{
                      marginBottom: 12,
                      padding: "8px 12px",
                      borderRadius: 8,
                      backgroundColor:
                        msg.role === "user" ? "var(--surface-card, #f5f5f5)" : "transparent",
                      border:
                        msg.role === "assistant"
                          ? "1px solid var(--border-color, #e8e8e8)"
                          : "none",
                    }}
                  >
                    <Text
                      strong
                      style={{
                        display: "block",
                        marginBottom: 4,
                        color:
                          msg.role === "user"
                            ? "var(--accent-default, #1677ff)"
                            : "var(--text-primary, #333)",
                      }}
                    >
                      {msg.role === "user" ? "🙋 你" : "🤖 AI"}
                    </Text>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            {isListening && (
              <div style={{ marginBottom: 8 }}>
                <Tag color="processing" icon={<AudioOutlined />} style={{ marginRight: 0 }}>
                  正在聆听... 1.5 秒无有效语音将自动暂停，点击麦克风可手动停止
                </Tag>
              </div>
            )}
            <Space.Compact style={{ width: "100%" }}>
              <Button
                type={isListening ? "primary" : "default"}
                icon={<AudioOutlined />}
                onClick={startVoiceInput}
                disabled={chatting}
                style={{
                  height: "auto",
                  background: isListening ? "var(--danger, #ff4d4f)" : undefined,
                  borderColor: isListening ? "var(--danger, #ff4d4f)" : undefined,
                }}
                title={
                  isListening
                    ? "停止语音输入（1.5 秒无语音自动暂停）"
                    : "语音输入（识别中文/英文）"
                }
              />
              <TextArea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendChat();
                  }
                }}
                placeholder="基于分析结果追问... (Enter 发送，Shift+Enter 换行)"
                rows={2}
                disabled={chatting}
                style={{ resize: "none" }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={sendChat}
                loading={chatting}
                disabled={!chatInput.trim()}
                style={{ height: "auto" }}
              />
            </Space.Compact>
          </Card>
        </>
      )}

      <style>{`
        .ai-report-content h1 { font-size: 1.6em; border-bottom: 2px solid var(--accent-default, #1677ff); padding-bottom: 8px; }
        .ai-report-content h2 { font-size: 1.3em; margin-top: 24px; }
        .ai-report-content h3 { font-size: 1.1em; margin-top: 16px; }
        .ai-report-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
        .ai-report-content th, .ai-report-content td { border: 1px solid #e8e8e8; padding: 8px 12px; text-align: left; }
        .ai-report-content th { background: #fafafa; font-weight: 600; }
        .ai-report-content blockquote { border-left: 3px solid var(--accent-default, #1677ff); padding-left: 12px; color: #666; margin: 12px 0; }
        .ai-report-content ul, .ai-report-content ol { padding-left: 20px; }
        .ai-report-content code { background: #f5f5f5; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
        .ai-report-content pre { background: #f8f8f8; border-radius: 8px; padding: 12px; overflow-x: auto; }
      `}</style>
    </div>
  );
};

export default AIAnalysis;
