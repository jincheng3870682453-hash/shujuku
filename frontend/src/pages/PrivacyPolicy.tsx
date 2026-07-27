/**
 * 隐私政策 & 使用教程页面
 *
 * 内容：
 * - AI 功能使用教程
 * - 隐私政策说明
 * - 数据安全说明
 */

import React from "react";
import { Card, Typography, Divider, Alert, Collapse, Tag } from "antd";
import {
  SafetyOutlined,
  ApiOutlined,
  LockOutlined,
  EyeOutlined,
  FileTextOutlined,
  KeyOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  SettingOutlined,
} from "@ant-design/icons";

const { Title, Text, Paragraph } = Typography;

export default function PrivacyPolicy() {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      {/* ── 标题 ── */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ marginBottom: 4 }}>
          <SafetyOutlined style={{ marginRight: 8, color: "#5e6ad2" }} />
          隐私政策 & 使用教程
        </Title>
        <Text type="secondary">
          了解 AI 分析功能的使用方法，以及我们如何保护您的数据安全
        </Text>
      </div>

      {/* ── 使用教程 ── */}
      <Card
        title={
          <span>
            <FileTextOutlined style={{ marginRight: 6, color: "#1677ff" }} />
            AI 数据分析使用教程
          </span>
        }
        style={{ marginBottom: 24 }}
        styles={{ body: { padding: "20px 24px" } }}
      >
        <Collapse
          defaultActiveKey={["1"]}
          items={[
            {
              key: "1",
              label: (
                <span>
                  <SettingOutlined style={{ marginRight: 6 }} />
                  <Text strong>第一步：配置 AI 模型</Text>
                </span>
              ),
              children: (
                <div style={{ lineHeight: 2, paddingLeft: 8 }}>
                  <Paragraph>
                    <Text strong>1. 选择 AI 服务商：</Text>点击「AI
                    分析」菜单进入页面，在配置面板中选择您要使用的 AI
                    服务商：
                  </Paragraph>
                  <ul style={{ paddingLeft: 20, marginBottom: 12 }}>
                    <li>
                      <Tag color="blue">OpenAI</Tag> — GPT-4.1 / o3
                      系列，综合能力最强，适合复杂分析
                    </li>
                    <li>
                      <Tag color="green">DeepSeek</Tag> —
                      国产高性价比模型，编程和推理能力强，价格实惠
                    </li>
                    <li>
                      <Tag color="purple">通义千问</Tag> —
                      阿里云 Qwen3 系列，中文理解出色
                    </li>
                    <li>
                      <Tag color="orange">文心一言</Tag> —
                      百度 ERNIE 系列，中文生态完善
                    </li>
                    <li>
                      <Tag>自定义</Tag> —
                      支持任何 OpenAI 兼容接口（如本地 Ollama、vLLM、第三方 API）
                    </li>
                  </ul>

                  <Paragraph>
                    <Text strong>2. 填写 API Key：</Text>
                    在"API Key"输入框中填入对应平台的 API 密钥。
                  </Paragraph>
                  <Alert
                    type="info"
                    showIcon
                    icon={<KeyOutlined />}
                    message="如何获取 API Key？"
                    description={
                      <div>
                        <Paragraph style={{ margin: "4px 0" }}>
                          • <Text strong>OpenAI：</Text>
                          访问{" "}
                          <a
                            href="https://platform.openai.com/api-keys"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            platform.openai.com/api-keys
                          </a>{" "}
                          创建
                        </Paragraph>
                        <Paragraph style={{ margin: "4px 0" }}>
                          • <Text strong>DeepSeek：</Text>
                          访问{" "}
                          <a
                            href="https://platform.deepseek.com/api_keys"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            platform.deepseek.com
                          </a>{" "}
                          创建
                        </Paragraph>
                        <Paragraph style={{ margin: "4px 0" }}>
                          • <Text strong>通义千问：</Text>
                          访问{" "}
                          <a
                            href="https://dashscope.console.aliyun.com/apiKey"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            阿里云 DashScope 控制台
                          </a>{" "}
                          获取
                        </Paragraph>
                        <Paragraph style={{ margin: "4px 0" }}>
                          • <Text strong>文心一言：</Text>
                          访问{" "}
                          <a
                            href="https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            百度千帆大模型平台
                          </a>{" "}
                          创建应用获取
                        </Paragraph>
                      </div>
                    }
                    style={{ marginBottom: 12 }}
                  />

                  <Paragraph>
                    <Text strong>3. 选择模型：</Text>
                    从下拉列表中选择模型（如 gpt-4.1-mini），也可以直接在输入框中输入自定义模型名后按回车。
                  </Paragraph>

                  <Paragraph>
                    <Text strong>4. 测试连接：</Text>
                    点击「测试连接」按钮验证配置是否正确。成功后会显示延迟时间。
                  </Paragraph>

                  <Alert
                    type="warning"
                    showIcon
                    message="测试连接失败的常见原因"
                    description={
                      <ul style={{ paddingLeft: 16, margin: 0 }}>
                        <li>API Key 填写错误或已过期</li>
                        <li>Base URL 地址不正确</li>
                        <li>网络无法访问目标地址（可能需要代理）</li>
                        <li>账户余额不足或配额已用完</li>
                        <li>对于自定义端点，确认服务是否已启动</li>
                      </ul>
                    }
                    style={{ marginTop: 8 }}
                  />
                </div>
              ),
            },
            {
              key: "2",
              label: (
                <span>
                  <ThunderboltOutlined style={{ marginRight: 6 }} />
                  <Text strong>第二步：执行分析</Text>
                </span>
              ),
              children: (
                <div style={{ lineHeight: 2, paddingLeft: 8 }}>
                  <Paragraph>
                    <Text strong>一键分析：</Text>
                    点击「一键分析」按钮，系统会自动：
                  </Paragraph>
                  <ol style={{ paddingLeft: 20, marginBottom: 12 }}>
                    <li>汇总数据库中所有表的数据统计</li>
                    <li>计算各字段的值分布、空值率、数值统计等</li>
                    <li>将统计结果发送给 AI 模型进行分析</li>
                    <li>返回结构化的分析报告（Markdown 格式）</li>
                  </ol>

                  <Paragraph>
                    <Text strong>带问题分析：</Text>
                    在输入框中填写您关心的问题（如"哪个部门人数最多？""最近一周的操作趋势是什么？"），AI
                    会针对性地回答。
                  </Paragraph>

                  <Paragraph>
                    <Text strong>对话追问：</Text>
                    分析完成后，可以在下方的对话框中继续追问，AI
                    会结合之前的分析上下文进行回答。
                  </Paragraph>
                </div>
              ),
            },
            {
              key: "3",
              label: (
                <span>
                  <CheckCircleOutlined style={{ marginRight: 6 }} />
                  <Text strong>第三步：查看和使用报告</Text>
                </span>
              ),
              children: (
                <div style={{ lineHeight: 2, paddingLeft: 8 }}>
                  <Paragraph>
                    <Text strong>报告展示：</Text>
                    分析结果以 Markdown
                    格式渲染展示，支持表格、代码块、列表等丰富格式。
                  </Paragraph>
                  <Paragraph>
                    <Text strong>复制报告：</Text>
                    点击「复制」按钮将报告内容复制到剪贴板。
                  </Paragraph>
                  <Paragraph>
                    <Text strong>清空重试：</Text>
                    点击「清空」按钮重置当前会话，重新开始分析。
                  </Paragraph>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* ── 隐私政策 ── */}
      <Card
        title={
          <span>
            <LockOutlined style={{ marginRight: 6, color: "#52c41a" }} />
            隐私政策 & 数据安全
          </span>
        }
        style={{ marginBottom: 24 }}
        styles={{ body: { padding: "20px 24px" } }}
      >
        <Paragraph>
          <Text strong style={{ fontSize: 15 }}>
            1. API Key 安全
          </Text>
        </Paragraph>
        <Paragraph>
          您的 API Key <Text strong>不会</Text>{" "}
          被存储在服务器或数据库中。API Key 仅保存在浏览器当前会话
          （sessionStorage）中，关闭浏览器标签页后自动清除。
        </Paragraph>
        <Paragraph>
          每次分析时，API Key 通过 HTTPS 加密传输到后端，用于调用 AI
          服务，<Text strong>不会被记录或存储</Text>。
        </Paragraph>

        <Divider />

        <Paragraph>
          <Text strong style={{ fontSize: 15 }}>
            2. 数据隐私
          </Text>
        </Paragraph>
        <Paragraph>
          当您使用 AI 分析功能时，系统会提取数据库中部分统计信息（如表名、列名、值分布、行数等）
          发送给 AI 模型进行处理。发送的数据 <Text strong>不包含原始记录的完整内容</Text>，
          仅包含聚合统计信息。
        </Paragraph>
        <Paragraph>
          如果您配置的是本地模型（如通过 Ollama
          部署），数据不会离开您的设备。
        </Paragraph>

        <Divider />

        <Paragraph>
          <Text strong style={{ fontSize: 15 }}>
            3. 数据库加密
          </Text>
        </Paragraph>
        <Paragraph>
          本系统支持 AES-256-GCM 数据库加密功能。启用后，数据库文件在磁盘上以加密形式存储，
          即使 U 盘丢失或设备被盗，未经授权的人员也无法读取数据内容。
        </Paragraph>
        <Paragraph>
          加密密钥由您自行设置和保管，系统不会存储明文密钥。
        </Paragraph>

        <Divider />

        <Paragraph>
          <Text strong style={{ fontSize: 15 }}>
            4. 用户责任
          </Text>
        </Paragraph>
        <Paragraph>
          使用 AI
          分析功能时，您应遵守所使用的第三方 AI 服务的使用条款和隐私政策。
        </Paragraph>
        <Paragraph>
          请不要在分析问题中直接输入敏感个人信息（如身份证号、银行账号等）。
        </Paragraph>

        <Alert
          type="success"
          showIcon
          icon={<EyeOutlined />}
          message="透明度承诺"
          description="本系统为开源项目，所有代码均可审计。如果您对数据处理有任何疑问，欢迎联系我们。"
        />
      </Card>

      {/* ── 技术说明 ── */}
      <Card
        title={
          <span>
            <ApiOutlined style={{ marginRight: 6, color: "#fa8c16" }} />
            技术说明
          </span>
        }
        style={{ marginBottom: 24 }}
        styles={{ body: { padding: "20px 24px" } }}
      >
        <Paragraph>
          <Text strong>支持的模型接口：</Text>OpenAI 兼容 API（/v1/chat/completions）
        </Paragraph>
        <Paragraph>
          <Text strong>模型预设（2026年7月更新）：</Text>
        </Paragraph>
        <ul>
          <li>
            <Text strong>OpenAI：</Text>gpt-4.1, gpt-4.1-mini, gpt-4.1-nano,
            gpt-4o, gpt-4o-mini, o4-mini, o3, o3-mini
          </li>
          <li>
            <Text strong>DeepSeek：</Text>deepseek-chat, deepseek-reasoner
          </li>
          <li>
            <Text strong>通义千问：</Text>qwen3-max, qwen3-plus, qwen3-turbo,
            qwen3-flash, qwen-plus, qwen-max, qwen-turbo
          </li>
          <li>
            <Text strong>文心一言：</Text>ernie-4.5-8k-preview, ernie-4.0-8k,
            ernie-4.0-turbo-8k, ernie-3.5-8k, ernie-speed-8k, ernie-lite-8k,
            ernie-tiny-8k
          </li>
          <li>
            <Text strong>自定义：</Text>任何兼容 OpenAI Chat Completions API
            的服务
          </li>
        </ul>
        <Paragraph type="secondary">
          注：所有模型名称均可在下拉框中选择，也支持手动输入自定义模型名。文心一言已从旧版非标接口切换为百度千帆 OpenAI 兼容接口（Base
          URL: qianfan.baidubce.com/v2）。
        </Paragraph>
      </Card>
    </div>
  );
}
