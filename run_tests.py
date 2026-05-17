"""运行测试脚本"""
import sys
import pytest

# 运行测试
exit_code = pytest.main([
    'tests/',
    '-v',
    '--tb=short',
    '--color=yes'
])

sys.exit(exit_code)
