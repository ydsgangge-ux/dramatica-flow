# 快速启动指南

## 🚀 5分钟快速上手

### 第一步：安装依赖

```bash
pip install fastapi uvicorn pydantic python-dotenv typer rich openai
```

### 第二步：选择 LLM 后端

#### 选项 A：使用 Ollama（本地，免费）

1. **安装 Ollama**
   - 访问 https://ollama.ai
   - 下载并安装

2. **下载模型**
   ```bash
   ollama pull llama3.1
   ```

3. **启动 Ollama 服务**
   ```bash
   ollama serve
   ```

4. **创建 .env 文件**
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.1
   ```

#### 选项 B：使用 DeepSeek API（云端，付费）

1. **获取 API Key**
   - 访问 https://platform.deepseek.com
   - 注册并获取 API Key

2. **创建 .env 文件**
   ```bash
   DEEPSEEK_API_KEY=your-api-key-here
   ```

### 第三步：启动 Web UI

#### Windows 用户

双击运行 `启动网页界面.bat`

#### 手动启动

```bash
# 终端1：启动后端服务器
python -m uvicorn core.server:app --reload --port 8766

# 终端2：打开浏览器
# 在浏览器中打开 dramatica_flow_web_ui.html
```

### 第四步：创建第一本书

```bash
# 创建书籍
df book --title "我的第一本小说" --genre "玄幻"

# 初始化配置
df setup init-templates 我的第一本小说

# 编辑配置文件
# 打开 books/我的第一本小说/setup/ 目录
# 编辑 characters.json, locations.json 等文件

# 加载配置
df setup load 我的第一本小说
```

### 第五步：开始写作

```bash
# 写第一章
df write 我的第一本小说

# 在 Web UI 中查看
# 刷新浏览器查看生成的章节
```

## 📋 完整流程示例

### 场景：创作一部玄幻小说

```bash
# 1. 创建书籍
df book --title "修仙之路" --genre "玄幻" --chapters 50

# 2. 初始化配置
df setup init-templates 修仙之路

# 3. 编辑角色配置
# 文件：books/修仙之路/setup/characters.json
{
  "characters": [
    {
      "id": "protagonist",
      "name": "林风",
      "role": "protagonist",
      "need": {
        "external": "成为最强修仙者",
        "internal": "证明自己的价值"
      },
      "arc": "从废材到天才的蜕变"
    },
    {
      "id": "antagonist",
      "name": "赵无忌",
      "role": "antagonist",
      "need": {
        "external": "阻止林风成长",
        "internal": "维护自己的地位"
      }
    }
  ]
}

# 4. 加载配置
df setup load 修仙之路

# 5. 开始写作
df write 修仙之路

# 6. 查看状态
df status 修仙之路

# 7. 在 Web UI 查看详情
# 打开浏览器查看因果链、情感弧线等

# 8. 审计和修订
df audit 修仙之路 1
df revise 修仙之路 1

# 9. 导出
df export 修仙之路
```

## 🎯 使用技巧

### 1. 选择合适的模型

| 任务 | 推荐模型 | 原因 |
|------|----------|------|
| 快速创作 | mistral:7b | 速度快，创意性好 |
| 高质量生成 | llama3.1:70b | 综合能力强 |
| 中文写作 | qwen2.5:14b | 中文理解最佳 |
| 审计修订 | deepseek-chat | 准确度高 |

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# LLM 配置
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
DEFAULT_TEMPERATURE=0.7

# 混合使用（可选）
AUDITOR_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your-key
```

### 3. Web UI 快捷操作

- **总览页面**：快速查看进度和统计
- **大纲页面**：按幕筛选查看情节
- **章节页面**：点击章节卡片审计
- **因果链**：理解故事逻辑
- **情感弧线**：切换角色查看
- **伏笔管理**：追踪未闭合伏笔
- **关系网络**：可视化角色关系

## 🔍 故障排除

### Ollama 连接失败

```bash
# 检查 Ollama 是否运行
curl http://localhost:11434/api/tags

# 如果无响应，启动服务
ollama serve
```

### API Key 无效

```bash
# 检查 .env 文件
cat .env

# 测试连接
df doctor
```

### Web UI 显示空白

```bash
# 确认服务器运行
# 访问 http://localhost:8766/api/books
# 应该返回 JSON 数据
```

## 📚 下一步

- 阅读 [完整文档](README.md)
- 查看 [Ollama 指南](docs/OLLAMA_GUIDE.md)
- 了解 [API 文档](docs/API.md)
- 运行 [测试套件](tests/)

## 💬 获取帮助

- GitHub Issues: https://github.com/your-repo/dramatica-flow/issues
- 文档: 查看 docs/ 目录

---

**祝创作愉快！** ✨
