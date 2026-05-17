# 更新日志

## [v1.1.0] - 2026-03-24

### ✨ 新功能

#### 🦙 Ollama 本地模型支持

- 新增 `OllamaProvider` 类，支持使用 Ollama 本地模型
- 支持所有 Ollama 兼容模型（llama3.1, mistral, qwen2.5 等）
- 可通过环境变量 `LLM_PROVIDER` 轻松切换模型
- 无需 API 费用，完全本地运行
- 新增 Ollama 使用指南文档 `docs/OLLAMA_GUIDE.md`

#### 🌐 Web UI 增强

- 完全重写 HTML 前端，移除 MOCK 数据
- 连接后端 REST API，实时获取数据
- 新增错误处理和加载状态显示
- 优化数据展示和用户体验

#### 🧪 测试套件

- 新增 `test_llm.py` - LLM 模块单元测试
- 新增 `test_server.py` - Web API 测试
- 新增 `test_integration.py` - 集成测试
- 覆盖 Ollama 和 DeepSeek Provider

#### 📝 文档改进

- 全新 README.md，包含完整使用说明
- Ollama 详细配置指南
- API 使用示例
- 故障排除说明

### 🔧 改进

- LLM Provider 工厂函数支持 provider_type 参数
- 优化导入结构和代码组织
- 增强错误处理和用户提示

### 📦 新增文件

```
tests/
  ├── __init__.py
  ├── test_llm.py
  ├── test_server.py
  └── test_integration.py

docs/
  └── OLLAMA_GUIDE.md

启动服务器.bat
启动网页界面.bat
demo_ollama.py
run_tests.py
README.md
```

### 🔄 修改文件

```
core/llm/__init__.py
  - 新增 OllamaProvider 类
  - 更新 create_provider 工厂函数
  - 支持 LLM_PROVIDER 环境变量

dramatica_flow_web_ui.html
  - 重写前端代码
  - 连接后端 API
  - 移除 MOCK 数据
  - 新增错误处理
```

## [v1.0.0] - 初始版本

### 功能

- Dramatica 叙事理论驱动
- 因果链管理系统
- 情感弧线追踪
- 伏笔埋设与回收
- 角色关系网络
- FastAPI REST API
- 基础 Web UI
- DeepSeek API 支持
- CLI 命令行工具

---

## 下一步计划

- [ ] 支持流式输出（streaming）
- [ ] 增加更多本地模型支持（vLLM, LocalAI）
- [ ] Web UI 实时协作功能
- [ ] 导出多种格式（EPUB, PDF）
- [ ] 多语言支持
- [ ] 性能优化和缓存机制
