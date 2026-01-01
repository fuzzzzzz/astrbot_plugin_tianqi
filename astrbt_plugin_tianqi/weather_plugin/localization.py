"""
本地化管理模块

处理多语言支持和文本本地化。
"""

import os
import yaml
from typing import Dict, Any, Optional
from .models import ConfigurationError


class LocalizationManager:
    """本地化管理器"""
    
    def __init__(self, locales_dir: str = None):
        """初始化本地化管理器"""
        self.locales_dir = locales_dir or os.path.join(os.path.dirname(__file__), 'locales')
        self._locales: Dict[str, Dict[str, Any]] = {}
        self._current_language = 'zh'  # 默认中文
        self._load_locales()
    
    def _load_locales(self) -> None:
        """加载所有本地化文件"""
        if not os.path.exists(self.locales_dir):
            return
        
        for filename in os.listdir(self.locales_dir):
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                lang_code = filename.split('.')[0]
                locale_path = os.path.join(self.locales_dir, filename)
                
                try:
                    with open(locale_path, 'r', encoding='utf-8') as f:
                        self._locales[lang_code] = yaml.safe_load(f) or {}
                except Exception as e:
                    raise ConfigurationError(f"加载本地化文件 {filename} 失败: {e}")
    
    def set_language(self, language: str) -> None:
        """设置当前语言"""
        if language not in self._locales:
            available = ', '.join(self._locales.keys())
            raise ConfigurationError(f"不支持的语言: {language}。可用语言: {available}")
        self._current_language = language
    
    def get_current_language(self) -> str:
        """获取当前语言"""
        return self._current_language
    
    def get_available_languages(self) -> list:
        """获取可用语言列表"""
        return list(self._locales.keys())
    
    def get_text(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        获取本地化文本
        
        Args:
            key: 文本键，支持点分隔的嵌套键，如 'messages.help'
            language: 语言代码，如果不提供则使用当前语言
            **kwargs: 用于格式化文本的参数
            
        Returns:
            本地化后的文本
        """
        lang = language or self._current_language
        
        if lang not in self._locales:
            # 回退到中文
            lang = 'zh'
            if lang not in self._locales:
                return key  # 如果连中文都没有，返回键名
        
        # 解析嵌套键
        value = self._locales[lang]
        for part in key.split('.'):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                # 如果当前语言没有该键，尝试回退到中文
                if lang != 'zh' and 'zh' in self._locales:
                    return self.get_text(key, 'zh', **kwargs)
                return key  # 找不到键，返回键名
        
        # 如果值是字符串，进行格式化
        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        
        return str(value)
    
    def get_metadata(self, language: Optional[str] = None) -> Dict[str, str]:
        """获取元数据本地化"""
        lang = language or self._current_language
        metadata = self.get_text('metadata', lang)
        
        if isinstance(metadata, dict):
            return metadata
        return {}
    
    def get_command_info(self, command: str, language: Optional[str] = None) -> Dict[str, str]:
        """获取命令信息本地化"""
        lang = language or self._current_language
        commands = self.get_text('commands', lang)
        
        if isinstance(commands, dict) and command in commands:
            return commands[command]
        return {}
    
    def format_message(self, message_key: str, language: Optional[str] = None, **kwargs) -> str:
        """格式化消息"""
        return self.get_text(f'messages.{message_key}', language, **kwargs)
    
    def format_error(self, error_key: str, language: Optional[str] = None, **kwargs) -> str:
        """格式化错误消息"""
        return self.get_text(f'messages.errors.{error_key}', language, **kwargs)
    
    def format_status(self, status_key: str, language: Optional[str] = None, **kwargs) -> str:
        """格式化状态消息"""
        return self.get_text(f'messages.status.{status_key}', language, **kwargs)
    
    def format_prompt(self, prompt_key: str, language: Optional[str] = None, **kwargs) -> str:
        """格式化提示消息"""
        return self.get_text(f'messages.prompts.{prompt_key}', language, **kwargs)
    
    def get_localized_metadata_from_file(self, metadata_path: str, language: Optional[str] = None) -> Dict[str, str]:
        """
        从元数据文件获取本地化信息
        
        Args:
            metadata_path: 元数据文件路径
            language: 语言代码
            
        Returns:
            本地化的元数据字典
        """
        lang = language or self._current_language
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
            
            # 获取本地化信息
            localization = metadata.get('localization', {})
            if lang in localization:
                return localization[lang]
            elif 'zh' in localization:
                return localization['zh']  # 回退到中文
            else:
                # 使用默认的 name 和 description
                return {
                    'name': metadata.get('name', ''),
                    'description': metadata.get('description', '')
                }
        except Exception:
            return {}
    
    def get_localized_command_info_from_file(self, metadata_path: str, command_name: str, language: Optional[str] = None) -> Dict[str, str]:
        """
        从元数据文件获取命令的本地化信息
        
        Args:
            metadata_path: 元数据文件路径
            command_name: 命令名称
            language: 语言代码
            
        Returns:
            本地化的命令信息字典
        """
        lang = language or self._current_language
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
            
            commands = metadata.get('commands', [])
            for command in commands:
                if command.get('name') == command_name:
                    # 获取本地化信息
                    localization = command.get('localization', {})
                    if lang in localization:
                        return localization[lang]
                    elif 'zh' in localization:
                        return localization['zh']  # 回退到中文
                    else:
                        # 使用默认信息
                        return {
                            'description': command.get('description', ''),
                            'usage': command.get('usage', '')
                        }
            
            return {}
        except Exception:
            return {}


# 全局本地化管理器实例
localization_manager = LocalizationManager()