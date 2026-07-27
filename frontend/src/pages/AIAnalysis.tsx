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
  Badge,
  Segmented,
  Modal,
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
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import httpClient from "../api/client";
import { useNavigate } from "react-router-dom";

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
}

const DEFAULT_CONFIG: AIConfig = {
  provider: "openai",
  model: "gpt-4.1-mini",
  api_key: "",
  base_url: "",
  temperature: 0.7,
};

const AIAnalysis: React.FC = () => {
  const navigate = useNavigate();
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── 状态 ──
  const [config, setConfig] = useState<AIConfig>(() => {
    try {
      const saved = sessionStorage.getItem("ai_config");
      return saved ? { ...DEFAULT_CONFIG, ...JSON.parse(saved) } : DEFAULT_CONFIG;
    } catch {
      return DEFAULT_CONFIG;
    }
  });
  const [modelsPresets, setModelsPresets] = useState<Record<string, ModelPreset>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [report, setReport] = useState<string>("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatting, setChatting] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "success" | "error">("idle");
  const [dataSummary, setDataSummary] = useState<string>("");

  // ── 加载模型预设 ──
  useEffect(() => {
    httpClient
      .get("/api/ai/models")
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

  // ── 自动滚动到底部 ──
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // ── 配置变更 ──
  const updateConfig = useCallback(
    (key: keyof AIConfig, value: string | number) => {
      setConfig((prev) => {
        const next = { ...prev, [key]: value };
        // 切换 provider 时自动选第一个模型
        if (key === "provider" && modelsPresets[value as string]) {
          next.model = modelsPresets[value as string].models[0];
          next.base_url = modelsPresets[value as string].base_url;
        }
        // 保存到 session（不持久化 API Key）
        const toSave = { ...next };
        if (!toSave.api_key) {
          // 不清除已有 key
        }
        try {
          sessionStorage.setItem("ai_config", JSON.stringify(toSave));
        } catch {}
        return next;
      });
      setConnectionStatus("idle");
    },
    [modelsPresets]
  );

  // 展示后端返回的具体错误信息（优先从 error.response.data 里取完整错误）
  const showError = (error: any, fallback: string) => {
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

  // ── 测试连接 ──
  const testConnection = async () => {
    if (!config.api_key) {
      message.warning("请先填写 API Key");
      return;
    }
    setTesting(true);
    setConnectionStatus("idle");
    try {
      const res: any = await httpClient.post("/api/ai/test", config);
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
  const startAnalysis = async (customQuestion?: string) => {
    if (!config.api_key) {
      message.warning("请先填写 API Key");
      setShowConfig(true);
      return;
    }
    setLoading(true);
    setReport("");
    setChatHistory([]);
    setDataSummary("");
    try {
      const res: any = await httpClient.post("/api/ai/analyze", {
        ...config,
        question: customQuestion || "",
      });
      if (res.success) {
        setReport(res.content);
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
  const sendChat = async () => {
    if (!chatInput.trim() || !config.api_key) return;
    const userMsg = chatInput.trim();
    setChatInput("");
    setChatHistory((prev) => [...prev, { role: "user", content: userMsg }]);
    setChatting(true);
    try {
      const res: any = await httpClient.post("/api/ai/chat", {
        ...config,
        history: chatHistory,
        message: userMsg,
      });
      if (res.success) {
        setChatHistory((prev) => [...prev, { role: "assistant", content: res.content }]);
      } else {
        setChatHistory((prev) => [...prev, { role: "assistant", content: `❌ 错误：${res.error}` }]);
      }
    } catch (e: any) {
      const errText = e?.response?.data?.error || e?.response?.data?.message || e?.message || "未知错误";
      setChatHistory((prev) => [...prev, { role: "assistant", content: `❌ 请求失败：${errText}` }]);
    } finally {
      setChatting(false);
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
                      autoComplete="off"
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
                    API Key 仅保存在当前会话中，关闭页面后自动清除
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
              </>
            )}
          </div>

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

            <Space.Compact style={{ width: "100%" }}>
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
