"""
天气警报管理器

负责检测、管理和发送天气警报通知。支持多种警报类型，
包括恶劣天气、温度变化、降水、风力和紫外线指数警报。
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .interfaces import IAlertManager
from .models import (
    WeatherAlert, AlertType, UserPrefs, WeatherData,
    WeatherError, ConfigurationError
)
from .localization import localization_manager


class AlertManager(IAlertManager):
    """天气警报管理器实现"""
    
    def __init__(self, db_path: str = "weather_alerts.db"):
        """
        初始化警报管理器
        
        Args:
            db_path: SQLite数据库文件路径
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        
        # 警报阈值配置
        self.alert_thresholds = {
            AlertType.SEVERE_WEATHER: {
                'wind_speed_ms': 17.0,  # 8级风以上 (m/s)
                'visibility_km': 1.0,   # 能见度低于1公里
                'conditions': ['thunderstorm', 'tornado', 'hurricane', 'blizzard']
            },
            AlertType.TEMPERATURE_CHANGE: {
                'daily_change_celsius': 10.0,  # 日温差超过10度
                'extreme_high_celsius': 35.0,  # 高温预警
                'extreme_low_celsius': -10.0   # 低温预警
            },
            AlertType.PRECIPITATION: {
                'heavy_rain_chance': 80,       # 降雨概率超过80%
                'snow_conditions': ['snow', 'heavy_snow', 'blizzard']
            },
            AlertType.WIND: {
                'strong_wind_ms': 13.9,       # 7级风以上
                'gale_wind_ms': 17.2          # 8级风以上
            },
            AlertType.UV_INDEX: {
                'high_uv': 8.0,               # 紫外线指数高
                'very_high_uv': 11.0          # 紫外线指数极高
            }
        }
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self) -> None:
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建用户订阅表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_subscriptions (
                        user_id TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, alert_type)
                    )
                ''')
                
                # 创建警报历史表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alert_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        location TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        start_time TEXT,
                        end_time TEXT
                    )
                ''')
                
                # 创建警报抑制表（防止重复发送）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alert_suppression (
                        user_id TEXT NOT NULL,
                        location TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        last_sent TEXT NOT NULL,
                        PRIMARY KEY (user_id, location, alert_type)
                    )
                ''')
                
                conn.commit()
                self.logger.info("警报管理器数据库初始化成功")
                
        except sqlite3.Error as e:
            self.logger.error(f"初始化警报数据库失败: {e}")
            raise ConfigurationError(f"无法初始化警报数据库: {e}")
    
    async def check_weather_alerts(self, location: str) -> List[WeatherAlert]:
        """
        检查指定位置的天气警报
        
        Args:
            location: 位置名称
            
        Returns:
            List[WeatherAlert]: 当前有效的天气警报列表
        """
        try:
            alerts = []
            
            # 这里应该调用天气API获取警报信息
            # 由于当前任务只实现AlertManager，暂时返回模拟数据
            # 在实际集成时，需要调用WeatherAPIClient获取真实警报数据
            
            # 模拟检查恶劣天气警报
            severe_alert = self._check_severe_weather_mock(location)
            if severe_alert:
                alerts.append(severe_alert)
            
            self.logger.debug(f"检查到 {len(alerts)} 个警报 (位置: {location})")
            return alerts
            
        except Exception as e:
            self.logger.error(f"检查天气警报时发生错误: {e}")
            raise WeatherError(f"无法检查天气警报: {e}")
    
    def _check_severe_weather_mock(self, location: str) -> Optional[WeatherAlert]:
        """模拟检查恶劣天气警报（占位符实现）"""
        # 这是一个占位符实现，在实际集成时会被替换
        # 实际实现应该基于真实的天气数据进行判断
        return None
    
    async def send_alert(self, user_id: str, alert: WeatherAlert) -> None:
        """
        发送警报给用户
        
        Args:
            user_id: 用户ID
            alert: 要发送的警报
        """
        try:
            # 检查是否应该发送此警报
            if not self._should_send_alert_internal(user_id, alert):
                self.logger.debug(f"跳过发送警报 (用户: {user_id}, 类型: {alert.alert_type})")
                return
            
            # 记录警报发送历史
            self._record_alert_history(user_id, alert)
            
            # 更新警报抑制记录
            self._update_alert_suppression(user_id, alert)
            
            # 实际发送逻辑将在集成时实现
            # 这里只记录日志
            self.logger.info(f"发送警报给用户 {user_id}: {alert.title}")
            
        except Exception as e:
            self.logger.error(f"发送警报时发生错误: {e}")
            raise WeatherError(f"无法发送警报: {e}")
    
    def subscribe_user(self, user_id: str, alert_types: List[AlertType]) -> None:
        """
        订阅用户警报
        
        Args:
            user_id: 用户ID
            alert_types: 要订阅的警报类型列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 先删除用户现有订阅
                cursor.execute(
                    'DELETE FROM user_subscriptions WHERE user_id = ?',
                    (user_id,)
                )
                
                # 添加新订阅
                for alert_type in alert_types:
                    cursor.execute(
                        '''INSERT INTO user_subscriptions 
                           (user_id, alert_type, created_at) 
                           VALUES (?, ?, ?)''',
                        (user_id, alert_type.value, datetime.now().isoformat())
                    )
                
                conn.commit()
                self.logger.info(f"用户 {user_id} 订阅了 {len(alert_types)} 种警报类型")
                
        except sqlite3.Error as e:
            self.logger.error(f"订阅用户警报时发生错误: {e}")
            raise WeatherError(f"无法订阅警报: {e}")
    
    def should_send_alert(self, alert: WeatherAlert, user_prefs: UserPrefs) -> bool:
        """
        判断是否应该发送警报
        
        Args:
            alert: 警报对象
            user_prefs: 用户偏好设置
            
        Returns:
            bool: 是否应该发送警报
        """
        try:
            # 检查用户是否订阅了此类型的警报
            if alert.alert_type not in user_prefs.alert_subscriptions:
                return False
            
            # 检查警报是否仍然有效
            if alert.end_time and alert.end_time < datetime.now():
                return False
            
            # 检查警报严重程度
            if alert.severity.lower() in ['low', '低']:
                return False  # 不发送低级别警报
            
            return True
            
        except Exception as e:
            self.logger.error(f"判断是否发送警报时发生错误: {e}")
            return False
    
    def _should_send_alert_internal(self, user_id: str, alert: WeatherAlert) -> bool:
        """内部方法：检查是否应该发送警报（包含抑制逻辑）"""
        try:
            # 检查警报抑制（防止短时间内重复发送）
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT last_sent FROM alert_suppression 
                       WHERE user_id = ? AND location = ? AND alert_type = ?''',
                    (user_id, alert.location, alert.alert_type.value)
                )
                
                result = cursor.fetchone()
                if result:
                    last_sent = datetime.fromisoformat(result[0])
                    # 同类型警报至少间隔1小时
                    if datetime.now() - last_sent < timedelta(hours=1):
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查警报抑制时发生错误: {e}")
            return True  # 出错时默认允许发送
    
    def _record_alert_history(self, user_id: str, alert: WeatherAlert) -> None:
        """记录警报发送历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO alert_history 
                       (user_id, alert_type, location, title, description, 
                        severity, sent_at, start_time, end_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        user_id,
                        alert.alert_type.value,
                        alert.location,
                        alert.title,
                        alert.description,
                        alert.severity,
                        datetime.now().isoformat(),
                        alert.start_time.isoformat(),
                        alert.end_time.isoformat() if alert.end_time else None
                    )
                )
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"记录警报历史时发生错误: {e}")
    
    def _update_alert_suppression(self, user_id: str, alert: WeatherAlert) -> None:
        """更新警报抑制记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT OR REPLACE INTO alert_suppression 
                       (user_id, location, alert_type, last_sent)
                       VALUES (?, ?, ?, ?)''',
                    (
                        user_id,
                        alert.location,
                        alert.alert_type.value,
                        datetime.now().isoformat()
                    )
                )
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"更新警报抑制记录时发生错误: {e}")
    
    def get_user_subscriptions(self, user_id: str) -> List[AlertType]:
        """
        获取用户的警报订阅
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[AlertType]: 用户订阅的警报类型列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT alert_type FROM user_subscriptions WHERE user_id = ?',
                    (user_id,)
                )
                
                results = cursor.fetchall()
                return [AlertType(row[0]) for row in results]
                
        except sqlite3.Error as e:
            self.logger.error(f"获取用户订阅时发生错误: {e}")
            return []
        except ValueError as e:
            self.logger.error(f"解析警报类型时发生错误: {e}")
            return []
    
    def get_alert_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户的警报历史
        
        Args:
            user_id: 用户ID
            limit: 返回记录数限制
            
        Returns:
            List[Dict[str, Any]]: 警报历史记录列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''SELECT alert_type, location, title, description, 
                              severity, sent_at, start_time, end_time
                       FROM alert_history 
                       WHERE user_id = ? 
                       ORDER BY sent_at DESC 
                       LIMIT ?''',
                    (user_id, limit)
                )
                
                results = cursor.fetchall()
                history = []
                
                for row in results:
                    history.append({
                        'alert_type': row[0],
                        'location': row[1],
                        'title': row[2],
                        'description': row[3],
                        'severity': row[4],
                        'sent_at': row[5],
                        'start_time': row[6],
                        'end_time': row[7]
                    })
                
                return history
                
        except sqlite3.Error as e:
            self.logger.error(f"获取警报历史时发生错误: {e}")
            return []
    
    def cleanup_old_alerts(self, days: int = 30) -> None:
        """
        清理旧的警报记录
        
        Args:
            days: 保留天数，超过此天数的记录将被删除
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 清理警报历史
                cursor.execute(
                    'DELETE FROM alert_history WHERE sent_at < ?',
                    (cutoff_date.isoformat(),)
                )
                
                # 清理警报抑制记录
                cursor.execute(
                    'DELETE FROM alert_suppression WHERE last_sent < ?',
                    (cutoff_date.isoformat(),)
                )
                
                conn.commit()
                self.logger.info(f"清理了 {days} 天前的警报记录")
                
        except sqlite3.Error as e:
            self.logger.error(f"清理警报记录时发生错误: {e}")
    
    def create_weather_alert(
        self,
        alert_type: AlertType,
        location: str,
        weather_data: WeatherData,
        **kwargs
    ) -> Optional[WeatherAlert]:
        """
        基于天气数据创建警报
        
        Args:
            alert_type: 警报类型
            location: 位置
            weather_data: 天气数据
            **kwargs: 额外参数
            
        Returns:
            Optional[WeatherAlert]: 创建的警报，如果不需要警报则返回None
        """
        try:
            if alert_type == AlertType.SEVERE_WEATHER:
                return self._create_severe_weather_alert(location, weather_data)
            elif alert_type == AlertType.TEMPERATURE_CHANGE:
                return self._create_temperature_alert(location, weather_data, **kwargs)
            elif alert_type == AlertType.WIND:
                return self._create_wind_alert(location, weather_data)
            elif alert_type == AlertType.UV_INDEX:
                return self._create_uv_alert(location, weather_data)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"创建警报时发生错误: {e}")
            return None
    
    def _create_severe_weather_alert(
        self,
        location: str,
        weather_data: WeatherData
    ) -> Optional[WeatherAlert]:
        """创建恶劣天气警报"""
        thresholds = self.alert_thresholds[AlertType.SEVERE_WEATHER]
        
        # 检查风速
        if weather_data.wind_speed >= thresholds['wind_speed_ms']:
            return WeatherAlert(
                alert_type=AlertType.SEVERE_WEATHER,
                title=localization_manager.format_message('alerts.severe_weather.high_wind_title'),
                description=localization_manager.format_message(
                    'alerts.severe_weather.high_wind_desc',
                    wind_speed=weather_data.wind_speed,
                    location=location
                ),
                severity="high",
                location=location,
                start_time=datetime.now(),
                advice=[
                    localization_manager.format_message('alerts.advice.avoid_outdoor'),
                    localization_manager.format_message('alerts.advice.secure_objects')
                ]
            )
        
        # 检查能见度
        if weather_data.visibility <= thresholds['visibility_km']:
            return WeatherAlert(
                alert_type=AlertType.SEVERE_WEATHER,
                title=localization_manager.format_message('alerts.severe_weather.low_visibility_title'),
                description=localization_manager.format_message(
                    'alerts.severe_weather.low_visibility_desc',
                    visibility=weather_data.visibility,
                    location=location
                ),
                severity="medium",
                location=location,
                start_time=datetime.now(),
                advice=[
                    localization_manager.format_message('alerts.advice.drive_carefully'),
                    localization_manager.format_message('alerts.advice.use_lights')
                ]
            )
        
        return None
    
    def _create_temperature_alert(
        self,
        location: str,
        weather_data: WeatherData,
        **kwargs
    ) -> Optional[WeatherAlert]:
        """创建温度警报"""
        thresholds = self.alert_thresholds[AlertType.TEMPERATURE_CHANGE]
        
        # 检查极端高温
        if weather_data.temperature >= thresholds['extreme_high_celsius']:
            return WeatherAlert(
                alert_type=AlertType.TEMPERATURE_CHANGE,
                title=localization_manager.format_message('alerts.temperature.high_temp_title'),
                description=localization_manager.format_message(
                    'alerts.temperature.high_temp_desc',
                    temperature=weather_data.temperature,
                    location=location
                ),
                severity="high",
                location=location,
                start_time=datetime.now(),
                advice=[
                    localization_manager.format_message('alerts.advice.stay_hydrated'),
                    localization_manager.format_message('alerts.advice.avoid_sun')
                ]
            )
        
        # 检查极端低温
        if weather_data.temperature <= thresholds['extreme_low_celsius']:
            return WeatherAlert(
                alert_type=AlertType.TEMPERATURE_CHANGE,
                title=localization_manager.format_message('alerts.temperature.low_temp_title'),
                description=localization_manager.format_message(
                    'alerts.temperature.low_temp_desc',
                    temperature=weather_data.temperature,
                    location=location
                ),
                severity="high",
                location=location,
                start_time=datetime.now(),
                advice=[
                    localization_manager.format_message('alerts.advice.dress_warmly'),
                    localization_manager.format_message('alerts.advice.avoid_prolonged_exposure')
                ]
            )
        
        return None
    
    def _create_wind_alert(
        self,
        location: str,
        weather_data: WeatherData
    ) -> Optional[WeatherAlert]:
        """创建风力警报"""
        thresholds = self.alert_thresholds[AlertType.WIND]
        
        if weather_data.wind_speed >= thresholds['gale_wind_ms']:
            severity = "high"
            title_key = 'alerts.wind.gale_title'
            desc_key = 'alerts.wind.gale_desc'
        elif weather_data.wind_speed >= thresholds['strong_wind_ms']:
            severity = "medium"
            title_key = 'alerts.wind.strong_title'
            desc_key = 'alerts.wind.strong_desc'
        else:
            return None
        
        return WeatherAlert(
            alert_type=AlertType.WIND,
            title=localization_manager.format_message(title_key),
            description=localization_manager.format_message(
                desc_key,
                wind_speed=weather_data.wind_speed,
                location=location
            ),
            severity=severity,
            location=location,
            start_time=datetime.now(),
            advice=[
                localization_manager.format_message('alerts.advice.secure_objects'),
                localization_manager.format_message('alerts.advice.avoid_outdoor')
            ]
        )
    
    def _create_uv_alert(
        self,
        location: str,
        weather_data: WeatherData
    ) -> Optional[WeatherAlert]:
        """创建紫外线警报"""
        thresholds = self.alert_thresholds[AlertType.UV_INDEX]
        
        if weather_data.uv_index >= thresholds['very_high_uv']:
            severity = "high"
            title_key = 'alerts.uv.very_high_title'
            desc_key = 'alerts.uv.very_high_desc'
        elif weather_data.uv_index >= thresholds['high_uv']:
            severity = "medium"
            title_key = 'alerts.uv.high_title'
            desc_key = 'alerts.uv.high_desc'
        else:
            return None
        
        return WeatherAlert(
            alert_type=AlertType.UV_INDEX,
            title=localization_manager.format_message(title_key),
            description=localization_manager.format_message(
                desc_key,
                uv_index=weather_data.uv_index,
                location=location
            ),
            severity=severity,
            location=location,
            start_time=datetime.now(),
            advice=[
                localization_manager.format_message('alerts.advice.use_sunscreen'),
                localization_manager.format_message('alerts.advice.wear_hat'),
                localization_manager.format_message('alerts.advice.seek_shade')
            ]
        )