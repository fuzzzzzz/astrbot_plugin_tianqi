"""
用户偏好管理实现

提供用户偏好的存储、检索和管理功能，支持默认位置、单位偏好和警报订阅。
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from .interfaces import IUserPreferences
from .models import UserPrefs, AlertType


class UserPreferences(IUserPreferences):
    """用户偏好管理器"""
    
    def __init__(self, db_path: str = "user_preferences.db"):
        """
        初始化用户偏好管理器
        
        Args:
            db_path: SQLite数据库文件路径
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self) -> None:
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    default_location TEXT,
                    units TEXT DEFAULT 'metric',
                    alert_subscriptions TEXT DEFAULT '[]',
                    language TEXT DEFAULT 'zh',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
    
    def get_user_preferences(self, user_id: str) -> UserPrefs:
        """
        获取用户偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户偏好对象，如果不存在则创建默认偏好
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # 解析警报订阅
                alert_subscriptions = []
                if row['alert_subscriptions']:
                    try:
                        alert_list = json.loads(row['alert_subscriptions'])
                        alert_subscriptions = [AlertType(alert) for alert in alert_list]
                    except (json.JSONDecodeError, ValueError):
                        alert_subscriptions = []
                
                # 解析时间戳
                created_at = None
                updated_at = None
                if row['created_at']:
                    try:
                        created_at = datetime.fromisoformat(row['created_at'])
                    except ValueError:
                        pass
                if row['updated_at']:
                    try:
                        updated_at = datetime.fromisoformat(row['updated_at'])
                    except ValueError:
                        pass
                
                return UserPrefs(
                    user_id=row['user_id'],
                    default_location=row['default_location'],
                    units=row['units'] or 'metric',
                    alert_subscriptions=alert_subscriptions,
                    language=row['language'] or 'zh',
                    created_at=created_at,
                    updated_at=updated_at
                )
            else:
                # 创建默认偏好并保存
                prefs = UserPrefs(user_id=user_id)
                self._save_preferences(prefs)
                return prefs
    
    def _save_preferences(self, prefs: UserPrefs) -> None:
        """
        保存用户偏好到数据库
        
        Args:
            prefs: 用户偏好对象
        """
        # 序列化警报订阅
        alert_subscriptions_json = json.dumps([alert.value for alert in prefs.alert_subscriptions])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences 
                (user_id, default_location, units, alert_subscriptions, language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                prefs.user_id,
                prefs.default_location,
                prefs.units,
                alert_subscriptions_json,
                prefs.language,
                prefs.created_at.isoformat() if prefs.created_at else None,
                prefs.updated_at.isoformat() if prefs.updated_at else None
            ))
            conn.commit()
    
    def set_default_location(self, user_id: str, location: str) -> None:
        """
        设置默认位置
        
        Args:
            user_id: 用户ID
            location: 位置名称
        """
        prefs = self.get_user_preferences(user_id)
        prefs.update_location(location)
        self._save_preferences(prefs)
    
    def set_units(self, user_id: str, units: str) -> None:
        """
        设置单位偏好
        
        Args:
            user_id: 用户ID
            units: 单位类型 ('metric' 或 'imperial')
        """
        prefs = self.get_user_preferences(user_id)
        prefs.update_units(units)
        self._save_preferences(prefs)
    
    def get_alert_subscriptions(self, user_id: str) -> List[AlertType]:
        """
        获取警报订阅
        
        Args:
            user_id: 用户ID
            
        Returns:
            警报类型列表
        """
        prefs = self.get_user_preferences(user_id)
        return prefs.alert_subscriptions
    
    def update_alert_subscriptions(self, user_id: str, alert_types: List[AlertType]) -> None:
        """
        更新警报订阅
        
        Args:
            user_id: 用户ID
            alert_types: 警报类型列表
        """
        prefs = self.get_user_preferences(user_id)
        prefs.alert_subscriptions = alert_types
        prefs.updated_at = datetime.now()
        self._save_preferences(prefs)
    
    def add_alert_subscription(self, user_id: str, alert_type: AlertType) -> None:
        """
        添加警报订阅
        
        Args:
            user_id: 用户ID
            alert_type: 警报类型
        """
        prefs = self.get_user_preferences(user_id)
        prefs.add_alert_subscription(alert_type)
        self._save_preferences(prefs)
    
    def remove_alert_subscription(self, user_id: str, alert_type: AlertType) -> None:
        """
        移除警报订阅
        
        Args:
            user_id: 用户ID
            alert_type: 警报类型
        """
        prefs = self.get_user_preferences(user_id)
        prefs.remove_alert_subscription(alert_type)
        self._save_preferences(prefs)
    
    def set_language(self, user_id: str, language: str) -> None:
        """
        设置语言偏好
        
        Args:
            user_id: 用户ID
            language: 语言代码 ('zh' 或 'en')
        """
        prefs = self.get_user_preferences(user_id)
        prefs.language = language
        prefs.updated_at = datetime.now()
        self._save_preferences(prefs)
    
    def delete_user_preferences(self, user_id: str) -> bool:
        """
        删除用户偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功删除
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_users(self) -> List[str]:
        """
        获取所有用户ID列表
        
        Returns:
            用户ID列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT user_id FROM user_preferences")
            return [row[0] for row in cursor.fetchall()]
    
    def cleanup_database(self) -> None:
        """清理数据库（用于测试）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_preferences")
            conn.commit()