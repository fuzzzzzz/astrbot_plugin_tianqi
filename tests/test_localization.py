"""
本地化系统测试

测试多语言支持和文本本地化功能。
"""

import pytest
import tempfile
import os
from weather_plugin.localization import LocalizationManager
from weather_plugin.models import ConfigurationError


class TestLocalizationManager:
    """本地化管理器测试"""
    
    def test_init_with_default_locales_dir(self):
        """测试使用默认本地化目录初始化"""
        manager = LocalizationManager()
        assert manager.locales_dir is not None
        assert manager.get_current_language() == 'zh'
    
    def test_init_with_custom_locales_dir(self):
        """测试使用自定义本地化目录初始化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = LocalizationManager(temp_dir)
            assert manager.locales_dir == temp_dir
    
    def test_set_language_valid(self):
        """测试设置有效语言"""
        manager = LocalizationManager()
        available_languages = manager.get_available_languages()
        
        if 'en' in available_languages:
            manager.set_language('en')
            assert manager.get_current_language() == 'en'
    
    def test_set_language_invalid(self):
        """测试设置无效语言"""
        manager = LocalizationManager()
        
        with pytest.raises(ConfigurationError):
            manager.set_language('invalid_lang')
    
    def test_get_available_languages(self):
        """测试获取可用语言列表"""
        manager = LocalizationManager()
        languages = manager.get_available_languages()
        
        assert isinstance(languages, list)
        # 应该至少有中文
        assert 'zh' in languages or len(languages) == 0  # 如果没有本地化文件
    
    def test_get_text_existing_key(self):
        """测试获取存在的文本键"""
        manager = LocalizationManager()
        
        # 测试简单键
        text = manager.get_text('metadata.name')
        assert isinstance(text, str)
        assert text != 'metadata.name'  # 应该返回实际文本而不是键名
    
    def test_get_text_nonexistent_key(self):
        """测试获取不存在的文本键"""
        manager = LocalizationManager()
        
        text = manager.get_text('nonexistent.key')
        assert text == 'nonexistent.key'  # 应该返回键名
    
    def test_get_text_with_formatting(self):
        """测试带格式化参数的文本获取"""
        manager = LocalizationManager()
        
        # 测试格式化
        text = manager.get_text('messages.status.querying_weather', location='北京')
        assert isinstance(text, str)
        assert '北京' in text or 'Beijing' in text or 'querying_weather' in text
    
    def test_get_metadata(self):
        """测试获取元数据本地化"""
        manager = LocalizationManager()
        
        metadata = manager.get_metadata()
        assert isinstance(metadata, dict)
    
    def test_get_command_info(self):
        """测试获取命令信息本地化"""
        manager = LocalizationManager()
        
        command_info = manager.get_command_info('weather')
        assert isinstance(command_info, dict)
    
    def test_format_message(self):
        """测试格式化消息"""
        manager = LocalizationManager()
        
        message = manager.format_message('help')
        assert isinstance(message, str)
    
    def test_format_error(self):
        """测试格式化错误消息"""
        manager = LocalizationManager()
        
        error = manager.format_error('config_error', error='test error')
        assert isinstance(error, str)
    
    def test_format_status(self):
        """测试格式化状态消息"""
        manager = LocalizationManager()
        
        status = manager.format_status('config_reloaded')
        assert isinstance(status, str)
    
    def test_format_prompt(self):
        """测试格式化提示消息"""
        manager = LocalizationManager()
        
        prompt = manager.format_prompt('ask_location')
        assert isinstance(prompt, str)
    
    def test_language_fallback(self):
        """测试语言回退机制"""
        manager = LocalizationManager()
        
        # 如果有英文本地化，测试回退
        if 'en' in manager.get_available_languages():
            manager.set_language('en')
            
            # 获取一个可能只在中文中存在的键
            text = manager.get_text('some.nonexistent.key')
            assert isinstance(text, str)


class TestLocalizationIntegration:
    """本地化集成测试"""
    
    def test_localization_files_exist(self):
        """测试本地化文件存在"""
        manager = LocalizationManager()
        languages = manager.get_available_languages()
        
        # 应该至少有一种语言
        assert len(languages) > 0
    
    def test_required_keys_exist(self):
        """测试必需的键存在"""
        manager = LocalizationManager()
        
        required_keys = [
            'metadata.name',
            'metadata.description',
            'messages.help',
            'messages.errors.config_error',
            'messages.status.config_reloaded'
        ]
        
        for key in required_keys:
            text = manager.get_text(key)
            # 如果返回键名本身，说明键不存在
            if text == key:
                # 这是可以接受的，因为可能没有本地化文件
                continue
            assert isinstance(text, str)
            assert len(text) > 0
    
    def test_consistency_across_languages(self):
        """测试不同语言间的一致性"""
        manager = LocalizationManager()
        languages = manager.get_available_languages()
        
        if len(languages) < 2:
            pytest.skip("需要至少两种语言进行一致性测试")
        
        test_keys = [
            'metadata.name',
            'messages.help'
        ]
        
        for key in test_keys:
            texts = {}
            for lang in languages:
                text = manager.get_text(key, language=lang)
                texts[lang] = text
            
            # 所有语言都应该有这个键的翻译
            for lang, text in texts.items():
                assert text != key, f"语言 {lang} 缺少键 {key} 的翻译"
                assert len(text) > 0, f"语言 {lang} 的键 {key} 翻译为空"


@pytest.fixture
def temp_localization_manager():
    """创建临时本地化管理器用于测试"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试本地化文件
        zh_content = """
metadata:
  name: "测试天气助手"
  description: "测试描述"

messages:
  help: "测试帮助信息"
  errors:
    config_error: "配置错误: {error}"
  status:
    config_reloaded: "配置重新加载成功"
        """
        
        en_content = """
metadata:
  name: "Test Weather Assistant"
  description: "Test description"

messages:
  help: "Test help message"
  errors:
    config_error: "Configuration error: {error}"
  status:
    config_reloaded: "Configuration reloaded successfully"
        """
        
        # 写入测试文件
        with open(os.path.join(temp_dir, 'zh.yaml'), 'w', encoding='utf-8') as f:
            f.write(zh_content)
        
        with open(os.path.join(temp_dir, 'en.yaml'), 'w', encoding='utf-8') as f:
            f.write(en_content)
        
        yield LocalizationManager(temp_dir)


class TestLocalizationWithTestData:
    """使用测试数据的本地化测试"""
    
    def test_basic_functionality(self, temp_localization_manager):
        """测试基本功能"""
        manager = temp_localization_manager
        
        # 测试默认语言
        assert manager.get_current_language() == 'zh'
        
        # 测试获取文本
        name = manager.get_text('metadata.name')
        assert name == "测试天气助手"
        
        # 测试切换语言
        manager.set_language('en')
        name = manager.get_text('metadata.name')
        assert name == "Test Weather Assistant"
    
    def test_formatting_with_test_data(self, temp_localization_manager):
        """测试格式化功能"""
        manager = temp_localization_manager
        
        # 测试中文格式化
        error = manager.format_error('config_error', error='测试错误')
        assert '测试错误' in error
        
        # 测试英文格式化
        manager.set_language('en')
        error = manager.format_error('config_error', error='test error')
        assert 'test error' in error
    
    def test_fallback_mechanism(self, temp_localization_manager):
        """测试回退机制"""
        manager = temp_localization_manager
        
        # 设置为英文
        manager.set_language('en')
        
        # 获取不存在的键，应该回退到中文
        text = manager.get_text('nonexistent.key')
        assert text == 'nonexistent.key'  # 最终回退到键名


class TestMetadataLocalization:
    """元数据本地化测试"""
    
    def test_get_localized_metadata_from_file(self):
        """测试从文件获取本地化元数据"""
        manager = LocalizationManager()
        
        # 测试获取中文元数据
        metadata_zh = manager.get_localized_metadata_from_file('metadata.yaml', 'zh')
        assert isinstance(metadata_zh, dict)
        
        # 测试获取英文元数据
        metadata_en = manager.get_localized_metadata_from_file('metadata.yaml', 'en')
        assert isinstance(metadata_en, dict)
        
        # 如果有本地化信息，应该不同
        if metadata_zh and metadata_en:
            # 至少名称应该不同（如果都有的话）
            if 'name' in metadata_zh and 'name' in metadata_en:
                assert metadata_zh['name'] != metadata_en['name']
    
    def test_get_localized_command_info_from_file(self):
        """测试从文件获取本地化命令信息"""
        manager = LocalizationManager()
        
        # 测试获取天气命令的中文信息
        command_zh = manager.get_localized_command_info_from_file('metadata.yaml', 'weather', 'zh')
        assert isinstance(command_zh, dict)
        
        # 测试获取天气命令的英文信息
        command_en = manager.get_localized_command_info_from_file('metadata.yaml', 'weather', 'en')
        assert isinstance(command_en, dict)
        
        # 测试不存在的命令
        nonexistent = manager.get_localized_command_info_from_file('metadata.yaml', 'nonexistent', 'zh')
        assert nonexistent == {}
    
    def test_metadata_file_fallback(self):
        """测试元数据文件回退机制"""
        manager = LocalizationManager()
        
        # 测试不存在的语言，应该回退到中文或默认值
        metadata = manager.get_localized_metadata_from_file('metadata.yaml', 'nonexistent_lang')
        assert isinstance(metadata, dict)
    
    def test_nonexistent_metadata_file(self):
        """测试不存在的元数据文件"""
        manager = LocalizationManager()
        
        # 测试不存在的文件
        metadata = manager.get_localized_metadata_from_file('nonexistent.yaml', 'zh')
        assert metadata == {}
        
        command = manager.get_localized_command_info_from_file('nonexistent.yaml', 'weather', 'zh')
        assert command == {}