"""
Ollama 接口演示脚本
演示如何使用 Ollama 本地模型进行文本生成
"""
import os
import sys

print("=" * 60)
print("  Dramatica-Flow Ollama 接口演示")
print("=" * 60)
print()

# 设置使用 Ollama
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL"] = "llama3.1"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"

try:
    from core.llm import OllamaProvider, LLMMessage, create_provider
    
    print("正在初始化 Ollama Provider...")
    print(f"模型: {os.environ.get('OLLAMA_MODEL')}")
    print(f"地址: {os.environ.get('OLLAMA_BASE_URL')}")
    print()
    
    # 方式1：直接创建
    print("方式1: 直接创建 OllamaProvider")
    provider = OllamaProvider()
    print(f"✓ Provider 创建成功")
    print(f"  - 模型: {provider.config.model}")
    print(f"  - 地址: {provider.config.base_url}")
    print(f"  - 温度: {provider.config.temperature}")
    print()
    
    # 方式2：通过工厂函数创建
    print("方式2: 通过 create_provider 工厂函数")
    provider2 = create_provider(provider_type="ollama")
    print(f"✓ Provider 创建成功")
    print()
    
    # 测试消息
    print("=" * 60)
    print("测试文本生成（需要 Ollama 服务运行中）")
    print("=" * 60)
    print()
    
    messages = [
        LLMMessage(role="system", content="你是一个专业的玄幻小说作家。"),
        LLMMessage(role="user", content="请用一句话描述一个少年在山巅修炼的场景。")
    ]
    
    print("发送消息:")
    print(f"  System: {messages[0].content}")
    print(f"  User: {messages[1].content}")
    print()
    print("等待响应...")
    
    try:
        response = provider.complete(messages)
        print()
        print("✓ 响应成功:")
        print("-" * 60)
        print(response.content)
        print("-" * 60)
        print()
        print(f"Token 使用: 输入 {response.input_tokens}, 输出 {response.output_tokens}")
        
    except Exception as e:
        print(f"✗ 生成失败: {e}")
        print()
        print("请确保 Ollama 服务正在运行:")
        print("  1. 安装 Ollama: https://ollama.ai")
        print("  2. 下载模型: ollama pull llama3.1")
        print("  3. 启动服务: ollama serve")
    
except ImportError as e:
    print(f"✗ 导入失败: {e}")
    print()
    print("请确保已安装所需依赖:")
    print("  pip install openai")
    
except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("演示完成")
print("=" * 60)
