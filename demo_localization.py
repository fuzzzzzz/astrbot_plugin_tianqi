#!/usr/bin/env python3
"""
本地化系统演示脚本

展示智能天气助手插件的多语言支持功能。
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weather_plugin.localization import LocalizationManager


def demo_basic_localization():
    """演示基本本地化功能"""
    print("=== 基本本地化功能演示 ===\n")
    
    manager = LocalizationManager()
    
    # 显示可用语言
    languages = manager.get_available_languages()
    print(f"可用语言: {', '.join(languages)}")
    print(f"当前语言: {manager.get_current_language()}\n")
    
    # 演示中文
    print("--- 中文 ---")
    manager.set_language('zh')
    print(f"插件名称: {manager.get_text('metadata.name')}")
    print(f"插件描述: {manager.get_text('metadata.description')}")
    print(f"帮助信息:\n{manager.format_message('help')}\n")
    
    # 演示英文（如果可用）
    if 'en' in languages:
        print("--- English ---")
        manager.set_language('en')
        print(f"Plugin Name: {manager.get_text('metadata.name')}")
        print(f"Plugin Description: {manager.get_text('metadata.description')}")
        print(f"Help Message:\n{manager.format_message('help')}\n")


def demo_message_formatting():
    """演示消息格式化功能"""
    print("=== 消息格式化演示 ===\n")
    
    manager = LocalizationManager()
    
    # 中文格式化
    print("--- 中文格式化 ---")
    manager.set_language('zh')
    print(f"查询天气: {manager.format_status('querying_weather', location='北京')}")
    print(f"配置错误: {manager.format_error('config_error', error='API密钥无效')}")
    print(f"配置重载: {manager.format_status('config_reloaded')}")
    print()
    
    # 英文格式化（如果可用）
    if 'en' in manager.get_available_languages():
        print("--- English Formatting ---")
        manager.set_language('en')
        print(f"Querying Weather: {manager.format_status('querying_weather', location='Beijing')}")
        print(f"Config Error: {manager.format_error('config_error', error='Invalid API key')}")
        print(f"Config Reloaded: {manager.format_status('config_reloaded')}")
        print()


def demo_metadata_localization():
    """演示元数据本地化功能"""
    print("=== 元数据本地化演示 ===\n")
    
    manager = LocalizationManager()
    
    # 从元数据文件获取本地化信息
    print("--- 从 metadata.yaml 获取本地化信息 ---")
    
    # 中文元数据
    metadata_zh = manager.get_localized_metadata_from_file('metadata.yaml', 'zh')
    print(f"中文插件名称: {metadata_zh.get('name', '未找到')}")
    print(f"中文插件描述: {metadata_zh.get('description', '未找到')}")
    
    # 英文元数据
    metadata_en = manager.get_localized_metadata_from_file('metadata.yaml', 'en')
    print(f"English Plugin Name: {metadata_en.get('name', 'Not found')}")
    print(f"English Plugin Description: {metadata_en.get('description', 'Not found')}")
    print()
    
    # 命令本地化
    print("--- 命令本地化信息 ---")
    
    # 天气命令
    weather_zh = manager.get_localized_command_info_from_file('metadata.yaml', 'weather', 'zh')
    weather_en = manager.get_localized_command_info_from_file('metadata.yaml', 'weather', 'en')
    
    print(f"天气命令 (中文): {weather_zh.get('description', '未找到')} - {weather_zh.get('usage', '未找到')}")
    print(f"Weather Command (English): {weather_en.get('description', 'Not found')} - {weather_en.get('usage', 'Not found')}")
    print()


def demo_fallback_mechanism():
    """演示回退机制"""
    print("=== 回退机制演示 ===\n")
    
    manager = LocalizationManager()
    
    # 测试不存在的键
    print("--- 不存在的键 ---")
    manager.set_language('zh')
    nonexistent = manager.get_text('nonexistent.key')
    print(f"不存在的键 'nonexistent.key': '{nonexistent}'")
    
    # 测试不存在的语言
    print("\n--- 不支持的语言回退 ---")
    try:
        manager.set_language('fr')  # 法语（不支持）
    except Exception as e:
        print(f"设置不支持的语言 'fr' 失败: {e}")
    
    # 测试语言回退
    if 'en' in manager.get_available_languages():
        manager.set_language('en')
        # 尝试获取可能只在中文中存在的键
        fallback_text = manager.get_text('some.chinese.only.key')
        print(f"英文环境下获取中文专有键: '{fallback_text}'")
    
    print()


def main():
    """主函数"""
    print("智能天气助手 - 本地化系统演示\n")
    print("=" * 50)
    
    try:
        demo_basic_localization()
        demo_message_formatting()
        demo_metadata_localization()
        demo_fallback_mechanism()
        
        print("演示完成！")
        
    except Exception as e:
        print(f"演示过程中发生错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())