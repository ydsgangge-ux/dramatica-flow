# Ollama 接口使用指南

## 概述

Dramatica-Flow 现已支持 Ollama 本地模型接口，让您可以使用本地部署的大语言模型进行写作。

## 安装 Ollama

1. 访问 [Ollama 官网](https://ollama.ai/)
2. 下载并安装适合您操作系统的版本
3. 安装完成后，打开终端运行：

```bash
ollama serve
```

## 下载模型

推荐使用以下模型：

```bash
# 下载 Llama 3.1 (推荐)
ollama pull llama3.1

# 或其他模型
ollama pull mistral
ollama pull codellama
ollama pull qwen2.5
```

## 配置 Dramatica-Flow

### 方式一：使用环境变量

在项目根目录创建 `.env` 文件：

```bash
# 使用 Ollama
LLM_PROVIDER=ollama

# Ollama 配置
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1

# 温度参数（可选）
DEFAULT_TEMPERATURE=0.7
```

### 方式二：在代码中指定

```python
from core.llm import create_provider, OllamaProvider

# 方式1：通过工厂函数
provider = create_provider(provider_type="ollama")

# 方式2：直接创建
from core.llm import LLMConfig
config = LLMConfig(
    api_key="ollama",
    base_url="http://localhost:11434/v1",
    model="llama3.1",
    temperature=0.7
)
provider = OllamaProvider(config)
```

## 使用示例

### CLI 命令

```bash
# 配置使用 Ollama
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=llama3.1

# 创建书籍
df book --title "我的小说" --genre "玄幻"

# 开始写作
df write my_book
```

### Python API

```python
from core.llm import OllamaProvider, LLMMessage

# 创建 provider
provider = OllamaProvider()

# 发送消息
messages = [
    LLMMessage(role="system", content="你是一个专业的小说作家。"),
    LLMMessage(role="user", content="请写一段玄幻小说的开头。")
]

response = provider.complete(messages)
print(response.content)
```

## 可用模型

### 推荐模型

| 模型 | 参数量 | 特点 | 推荐场景 |
|------|--------|------|----------|
| llama3.1 | 8B/70B | 综合能力强，支持128K上下文 | 通用写作 |
| mistral | 7B | 轻量高效，创意性好 | 快速创作 |
| qwen2.5 | 7B/14B | 中文能力强 | 中文写作 |
| codellama | 7B/34B | 代码理解强 | 技术文档 |

### 模型性能对比

| 模型 | 响应速度 | 创意性 | 中文能力 | 内存占用 |
|------|----------|--------|----------|----------|
| llama3.1:8b | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ~8GB |
| mistral:7b | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ~6GB |
| qwen2.5:7b | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~8GB |

## 高级配置

### 自定义 Ollama 服务器

如果 Ollama 运行在远程服务器：

```bash
OLLAMA_BASE_URL=http://your-server:11434/v1
```

### 调整模型参数

```bash
# 温度（0-1，越高越随机）
DEFAULT_TEMPERATURE=0.8

# 最大输出长度
OLLAMA_MAX_TOKENS=4096
```

### 混合使用多个模型

您可以为不同任务配置不同模型：

```python
# 写作用 Ollama
writer_llm = create_provider(provider_type="ollama")

# 审计用 DeepSeek（如果需要更高准确度）
auditor_llm = create_provider(provider_type="deepseek")
```

## 故障排除

### Ollama 无法连接

检查 Ollama 是否正在运行：

```bash
curl http://localhost:11434/api/tags
```

### 内存不足

使用较小的量化模型：

```bash
ollama pull llama3.1:7b-q4_0
```

### 响应速度慢

1. 使用 GPU 加速（如果有）
2. 减小模型大小
3. 降低 max_tokens

## 性能优化建议

1. **使用 GPU**：确保 Ollama 使用 GPU 加速
2. **批量处理**：一次生成多个章节大纲
3. **模型选择**：根据任务选择合适大小的模型
4. **缓存策略**：重复使用相同上下文时考虑缓存

## 切换回 DeepSeek

如果需要切换回 DeepSeek：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=your-api-key
```

## 更多信息

- [Ollama 官方文档](https://github.com/ollama/ollama)
- [Dramatica-Flow 文档](./README.md)
- [常见问题](./FAQ.md)
