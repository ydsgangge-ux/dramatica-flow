"""检查导入问题"""
import sys
import traceback

try:
    print("导入 core.llm...")
    from core.llm import OllamaProvider, create_provider
    print("✓ core.llm 导入成功")
    
    print("\n导入 core.server...")
    from core.server import app
    print("✓ core.server 导入成功")
    
    print("\n导入 core.state...")
    from core.state import StateManager
    print("✓ core.state 导入成功")
    
    print("\n创建 OllamaProvider...")
    provider = OllamaProvider()
    print(f"✓ OllamaProvider 创建成功: {provider.config.model}")
    
    print("\n所有导入测试通过！")
    
except Exception as e:
    print(f"\n✗ 错误: {e}")
    traceback.print_exc()
    sys.exit(1)
