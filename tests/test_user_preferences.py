"""
用户偏好管理测试
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from weather_plugin.user_preferences import UserPreferences
from weather_plugin.models import UserPrefs, AlertType


class TestUserPreferences:
    """用户偏好管理测试"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # 清理 - 在Windows上可能需要多次尝试
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            # Windows上SQLite文件可能被锁定，忽略删除错误
            pass
    
    @pytest.fixture
    def user_prefs_manager(self, temp_db):
        """创建用户偏好管理器"""
        return UserPreferences(temp_db)
    
    def test_init_database(self, user_prefs_manager):
        """测试数据库初始化"""
        # 数据库文件应该存在
        assert user_prefs_manager.db_path.exists()
    
    def test_get_new_user_preferences(self, user_prefs_manager):
        """测试获取新用户偏好"""
        prefs = user_prefs_manager.get_user_preferences("new_user")
        
        assert prefs.user_id == "new_user"
        assert prefs.units == "metric"
        assert prefs.language == "zh"
        assert prefs.alert_subscriptions == []
        assert prefs.default_location is None
        assert prefs.created_at is not None
        assert prefs.updated_at is not None
    
    def test_set_default_location(self, user_prefs_manager):
        """测试设置默认位置"""
        user_id = "test_user"
        location = "北京"
        
        user_prefs_manager.set_default_location(user_id, location)
        prefs = user_prefs_manager.get_user_preferences(user_id)
        
        assert prefs.default_location == location
    
    def test_set_units(self, user_prefs_manager):
        """测试设置单位偏好"""
        user_id = "test_user"
        
        user_prefs_manager.set_units(user_id, "imperial")
        prefs = user_prefs_manager.get_user_preferences(user_id)
        
        assert prefs.units == "imperial"
    
    def test_invalid_units(self, user_prefs_manager):
        """测试无效单位"""
        user_id = "test_user"
        
        with pytest.raises(ValueError):
            user_prefs_manager.set_units(user_id, "invalid")
    
    def test_alert_subscriptions(self, user_prefs_manager):
        """测试警报订阅管理"""
        user_id = "test_user"
        
        # 添加订阅
        user_prefs_manager.add_alert_subscription(user_id, AlertType.SEVERE_WEATHER)
        subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
        assert AlertType.SEVERE_WEATHER in subscriptions
        
        # 添加另一个订阅
        user_prefs_manager.add_alert_subscription(user_id, AlertType.TEMPERATURE_CHANGE)
        subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
        assert len(subscriptions) == 2
        
        # 移除订阅
        user_prefs_manager.remove_alert_subscription(user_id, AlertType.SEVERE_WEATHER)
        subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
        assert AlertType.SEVERE_WEATHER not in subscriptions
        assert AlertType.TEMPERATURE_CHANGE in subscriptions
    
    def test_update_alert_subscriptions(self, user_prefs_manager):
        """测试批量更新警报订阅"""
        user_id = "test_user"
        alert_types = [AlertType.SEVERE_WEATHER, AlertType.UV_INDEX]
        
        user_prefs_manager.update_alert_subscriptions(user_id, alert_types)
        subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
        
        assert len(subscriptions) == 2
        assert AlertType.SEVERE_WEATHER in subscriptions
        assert AlertType.UV_INDEX in subscriptions
    
    def test_set_language(self, user_prefs_manager):
        """测试设置语言偏好"""
        user_id = "test_user"
        
        user_prefs_manager.set_language(user_id, "en")
        prefs = user_prefs_manager.get_user_preferences(user_id)
        
        assert prefs.language == "en"
    
    def test_delete_user_preferences(self, user_prefs_manager):
        """测试删除用户偏好"""
        user_id = "test_user"
        
        # 创建用户偏好
        user_prefs_manager.set_default_location(user_id, "北京")
        
        # 确认存在
        prefs = user_prefs_manager.get_user_preferences(user_id)
        assert prefs.default_location == "北京"
        
        # 删除
        result = user_prefs_manager.delete_user_preferences(user_id)
        assert result is True
        
        # 再次获取应该是新的默认偏好
        prefs = user_prefs_manager.get_user_preferences(user_id)
        assert prefs.default_location is None
    
    def test_get_all_users(self, user_prefs_manager):
        """测试获取所有用户"""
        user_ids = ["user1", "user2", "user3"]
        
        # 创建用户偏好
        for user_id in user_ids:
            user_prefs_manager.set_default_location(user_id, "北京")
        
        all_users = user_prefs_manager.get_all_users()
        
        assert len(all_users) == 3
        for user_id in user_ids:
            assert user_id in all_users
    
    def test_persistence(self, user_prefs_manager):
        """测试数据持久化"""
        user_id = "test_user"
        location = "上海"
        
        # 设置偏好
        user_prefs_manager.set_default_location(user_id, location)
        user_prefs_manager.set_units(user_id, "imperial")
        user_prefs_manager.add_alert_subscription(user_id, AlertType.SEVERE_WEATHER)
        
        # 创建新的管理器实例（模拟重启）
        new_manager = UserPreferences(user_prefs_manager.db_path)
        prefs = new_manager.get_user_preferences(user_id)
        
        assert prefs.default_location == location
        assert prefs.units == "imperial"
        assert AlertType.SEVERE_WEATHER in prefs.alert_subscriptions
    
    def test_cleanup_database(self, user_prefs_manager):
        """测试数据库清理"""
        # 创建一些用户偏好
        user_prefs_manager.set_default_location("user1", "北京")
        user_prefs_manager.set_default_location("user2", "上海")
        
        # 确认存在
        all_users = user_prefs_manager.get_all_users()
        assert len(all_users) == 2
        
        # 清理
        user_prefs_manager.cleanup_database()
        
        # 确认清理完成
        all_users = user_prefs_manager.get_all_users()
        assert len(all_users) == 0