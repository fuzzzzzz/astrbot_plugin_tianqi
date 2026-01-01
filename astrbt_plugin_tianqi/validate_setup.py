#!/usr/bin/env python3
"""
项目结构验证脚本

验证天气插件的基本结构和配置是否正确。
"""

import os
import sys
import importlib.util
from pathlib import Path


def check_file_exists(filepath: str, description: str) -> bool:
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} (缺失)")
        return False


def check_directory_exists(dirpath: str, description: str) -> bool:
    """检查目录是否存在"""
    if os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description}: {dirpath} (缺失)")
        return False


def check_python_import(module_name: str, description: str) -> bool:
    """检查 Python 模块是否可以导入"""
    try:
        __import__(module_name)
        print(f"✅ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {module_name} (导入失败: {e})")
        return False


def main():
    """主验证函数"""
    print("🔍 验证天气插件项目结构...")
    print("=" * 50)
    
    all_checks_passed = True
    
    # 检查核心目录
    print("\n📁 核心目录结构:")
    all_checks_passed &= check_directory_exists("weather_plugin", "插件包目录")
    all_checks_passed &= check_directory_exists("tests", "测试目录")
    
    # 检查核心文件
    print("\n📄 核心文件:")
    all_checks_passed &= check_file_exists("weather_plugin/__init__.py", "插件包初始化")
    all_checks_passed &= check_file_exists("weather_plugin/plugin.py", "主插件类")
    all_checks_passed &= check_file_exists("weather_plugin/models.py", "数据模型")
    all_checks_passed &= check_file_exists("weather_plugin/interfaces.py", "接口定义")
    all_checks_passed &= check_file_exists("weather_plugin/config.py", "配置管理")
    
    # 检查配置文件
    print("\n⚙️ 配置文件:")
    all_checks_passed &= check_file_exists("metadata.yaml", "插件元数据")
    all_checks_passed &= check_file_exists("config.yaml", "插件配置")
    all_checks_passed &= check_file_exists("requirements.txt", "依赖项列表")
    all_checks_passed &= check_file_exists("pytest.ini", "测试配置")
    
    # 检查测试文件
    print("\n🧪 测试文件:")
    all_checks_passed &= check_file_exists("tests/__init__.py", "测试包初始化")
    all_checks_passed &= check_file_exists("tests/conftest.py", "测试配置")
    all_checks_passed &= check_file_exists("tests/test_models.py", "模型测试")
    all_checks_passed &= check_file_exists("tests/test_config.py", "配置测试")
    all_checks_passed &= check_file_exists("tests/test_plugin.py", "插件测试")
    
    # 检查 Python 模块导入
    print("\n🐍 Python 模块导入:")
    all_checks_passed &= check_python_import("weather_plugin", "插件包")
    all_checks_passed &= check_python_import("weather_plugin.models", "数据模型")
    all_checks_passed &= check_python_import("weather_plugin.config", "配置管理")
    all_checks_passed &= check_python_import("weather_plugin.plugin", "主插件")
    
    # 检查插件类
    print("\n🔌 插件类验证:")
    try:
        from weather_plugin.plugin import WeatherPlugin, create_plugin
        print("✅ WeatherPlugin 类导入成功")
        print("✅ create_plugin 函数导入成功")
        
        # 尝试创建插件实例（使用测试配置）
        test_config = {
            'api_key': 'test_key',
            'api_provider': 'openweathermap'
        }
        plugin = WeatherPlugin(test_config)
        print("✅ WeatherPlugin 实例创建成功")
        
    except Exception as e:
        print(f"❌ 插件类验证失败: {e}")
        all_checks_passed = False
    
    # 总结
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 所有检查通过！项目结构设置正确。")
        print("\n📋 下一步:")
        print("1. 配置 API 密钥在 config.yaml 中")
        print("2. 运行测试: pytest tests/")
        print("3. 开始实现具体功能")
        return 0
    else:
        print("⚠️ 发现问题，请检查上述错误并修复。")
        return 1


if __name__ == "__main__":
    sys.exit(main())