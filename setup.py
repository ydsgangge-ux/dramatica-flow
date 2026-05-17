"""
Dramatica-Flow 快速安装入口
用法: pip install -e .
     或: python setup.py
"""
import subprocess
import sys
import os


def main():
    print("Dramatica-Flow 安装程序")
    print("=" * 50)
    
    # 安装当前包为可编辑模式
    print("\n[1/2] 安装依赖包...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-e", "."
    ])
    
    # 验证
    print("\n[2/2] 验证安装...")
    try:
        import openai, pydantic, fastapi, uvicorn, typer, rich, dotenv
        print("  所有模块导入成功!")
    except ImportError as e:
        print(f"  [错误] 模块导入失败: {e}")
        sys.exit(1)
    
    print("\n安装完成! 使用方式:")
    print("  python -m uvicorn core.server:app --reload --port 8766")
    print("  或双击 '启动网页界面.bat'")


if __name__ == "__main__":
    main()
