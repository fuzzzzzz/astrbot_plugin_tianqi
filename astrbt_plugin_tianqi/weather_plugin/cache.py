"""
缓存管理模块

实现基于SQLite的智能缓存管理系统，支持TTL管理和自动清理。
"""

import sqlite3
import json
import hashlib
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .interfaces import ICacheManager
from .models import WeatherData, ForecastData, CacheError
from .config import WeatherConfig


class CacheManager(ICacheManager):
    """SQLite缓存管理器实现"""
    
    def __init__(self, config: WeatherConfig):
        """
        初始化缓存管理器
        
        Args:
            config: 天气配置对象
        """
        self.config = config
        self.db_path = config.cache_db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        
        # 自动清理相关
        self._cleanup_thread: Optional[threading.Thread] = None
        self._cleanup_interval = 3600  # 1小时清理一次
        self._stop_cleanup = threading.Event()
        self._cleanup_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # 确保数据库目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        # 启动自动清理
        self.start_auto_cleanup()
    
    def _init_database(self) -> None:
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS weather_cache (
                        cache_key TEXT PRIMARY KEY,
                        data_type TEXT NOT NULL,
                        location TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        access_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP
                    )
                """)
                
                # 创建索引以提高查询性能
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires_at 
                    ON weather_cache(expires_at)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_location_type 
                    ON weather_cache(location, data_type)
                """)
                
                conn.commit()
                
        except sqlite3.Error as e:
            raise CacheError(f"初始化数据库失败: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise CacheError(f"连接数据库失败: {e}")
    
    async def get_cached_weather(self, cache_key: str) -> Optional[WeatherData]:
        """
        获取缓存的天气数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存的天气数据，如果不存在或已过期则返回None
        """
        if not self.config.cache_enabled:
            return None
            
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT data_json, expires_at, access_count
                        FROM weather_cache 
                        WHERE cache_key = ? AND data_type = 'weather'
                    """, (cache_key,))
                    
                    row = cursor.fetchone()
                    if not row:
                        return None
                    
                    # 检查是否过期
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if datetime.now() > expires_at:
                        # 删除过期数据
                        conn.execute("DELETE FROM weather_cache WHERE cache_key = ?", (cache_key,))
                        conn.commit()
                        return None
                    
                    # 更新访问统计
                    conn.execute("""
                        UPDATE weather_cache 
                        SET access_count = access_count + 1, last_accessed = ?
                        WHERE cache_key = ?
                    """, (datetime.now().isoformat(), cache_key))
                    conn.commit()
                    
                    # 反序列化数据
                    data_dict = json.loads(row['data_json'])
                    return WeatherData.from_dict(data_dict)
                
            except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
                raise CacheError(f"获取缓存天气数据失败: {e}")
    
    async def cache_weather_data(self, cache_key: str, data: WeatherData, ttl: int) -> None:
        """
        缓存天气数据
        
        Args:
            cache_key: 缓存键
            data: 天气数据
            ttl: 生存时间（秒）
        """
        if not self.config.cache_enabled:
            return
            
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    now = datetime.now()
                    expires_at = now + timedelta(seconds=ttl)
                    
                    # 序列化数据
                    data_json = data.to_json()
                    
                    # 插入或更新缓存
                    conn.execute("""
                        INSERT OR REPLACE INTO weather_cache 
                        (cache_key, data_type, location, data_json, created_at, expires_at, access_count, last_accessed)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        cache_key, 'weather', data.location, data_json,
                        now.isoformat(), expires_at.isoformat(), now.isoformat()
                    ))
                    
                    conn.commit()
                
            except (sqlite3.Error, json.JSONEncodeError) as e:
                raise CacheError(f"缓存天气数据失败: {e}")
    
    async def get_cached_forecast(self, cache_key: str) -> Optional[ForecastData]:
        """
        获取缓存的预报数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存的预报数据，如果不存在或已过期则返回None
        """
        if not self.config.cache_enabled:
            return None
            
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT data_json, expires_at, access_count
                        FROM weather_cache 
                        WHERE cache_key = ? AND data_type = 'forecast'
                    """, (cache_key,))
                    
                    row = cursor.fetchone()
                    if not row:
                        return None
                    
                    # 检查是否过期
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if datetime.now() > expires_at:
                        # 删除过期数据
                        conn.execute("DELETE FROM weather_cache WHERE cache_key = ?", (cache_key,))
                        conn.commit()
                        return None
                    
                    # 更新访问统计
                    conn.execute("""
                        UPDATE weather_cache 
                        SET access_count = access_count + 1, last_accessed = ?
                        WHERE cache_key = ?
                    """, (datetime.now().isoformat(), cache_key))
                    conn.commit()
                    
                    # 反序列化数据
                    data_dict = json.loads(row['data_json'])
                    return ForecastData.from_dict(data_dict)
                
            except (sqlite3.Error, json.JSONDecodeError, ValueError) as e:
                raise CacheError(f"获取缓存预报数据失败: {e}")
    
    async def cache_forecast_data(self, cache_key: str, data: ForecastData, ttl: int) -> None:
        """
        缓存预报数据
        
        Args:
            cache_key: 缓存键
            data: 预报数据
            ttl: 生存时间（秒）
        """
        if not self.config.cache_enabled:
            return
            
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    now = datetime.now()
                    expires_at = now + timedelta(seconds=ttl)
                    
                    # 序列化数据
                    data_json = data.to_json()
                    
                    # 插入或更新缓存
                    conn.execute("""
                        INSERT OR REPLACE INTO weather_cache 
                        (cache_key, data_type, location, data_json, created_at, expires_at, access_count, last_accessed)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        cache_key, 'forecast', data.location, data_json,
                        now.isoformat(), expires_at.isoformat(), now.isoformat()
                    ))
                    
                    conn.commit()
                
            except (sqlite3.Error, json.JSONEncodeError) as e:
                raise CacheError(f"缓存预报数据失败: {e}")
    
    def generate_cache_key(self, location: str, data_type: str, **kwargs) -> str:
        """
        生成缓存键
        
        Args:
            location: 位置
            data_type: 数据类型 ('weather', 'forecast', 'hourly')
            **kwargs: 额外参数（如days, hours, units等）
            
        Returns:
            生成的缓存键
        """
        # 标准化位置名称（转小写，去除空格）
        normalized_location = location.lower().strip().replace(' ', '_')
        
        # 构建键组件
        key_components = [normalized_location, data_type]
        
        # 添加额外参数
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            key_components.append(f"{key}:{value}")
        
        # 生成哈希
        key_string = "|".join(key_components)
        hash_object = hashlib.md5(key_string.encode('utf-8'))
        
        return f"weather_cache:{hash_object.hexdigest()}"
    
    def cleanup_expired_cache(self) -> None:
        """清理过期缓存"""
        try:
            with self._get_connection() as conn:
                now = datetime.now().isoformat()
                
                # 获取清理前统计
                cursor = conn.execute("SELECT COUNT(*) as total FROM weather_cache")
                total_before = cursor.fetchone()['total']
                
                cursor = conn.execute("""
                    SELECT COUNT(*) as expired 
                    FROM weather_cache 
                    WHERE expires_at < ?
                """, (now,))
                expired_count = cursor.fetchone()['expired']
                
                # 删除过期记录
                cursor = conn.execute("""
                    DELETE FROM weather_cache 
                    WHERE expires_at < ?
                """, (now,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                # 记录清理统计
                cleanup_stats = {
                    'timestamp': datetime.now().isoformat(),
                    'total_before': total_before,
                    'expired_found': expired_count,
                    'deleted_count': deleted_count,
                    'total_after': total_before - deleted_count
                }
                
                # 调用回调函数（如果设置了）
                if self._cleanup_callback:
                    self._cleanup_callback(cleanup_stats)
                
                if deleted_count > 0:
                    print(f"缓存清理完成: 删除了 {deleted_count} 条过期记录")
                
        except sqlite3.Error as e:
            raise CacheError(f"清理过期缓存失败: {e}")
    
    def start_auto_cleanup(self) -> None:
        """启动自动清理线程"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._stop_cleanup.clear()
            self._cleanup_thread = threading.Thread(
                target=self._auto_cleanup_worker,
                daemon=True,
                name="CacheCleanupWorker"
            )
            self._cleanup_thread.start()
    
    def stop_auto_cleanup(self) -> None:
        """停止自动清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5.0)
    
    def set_cleanup_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        设置清理回调函数
        
        Args:
            callback: 清理完成后调用的回调函数，接收清理统计信息
        """
        self._cleanup_callback = callback
    
    def set_cleanup_interval(self, interval_seconds: int) -> None:
        """
        设置自动清理间隔
        
        Args:
            interval_seconds: 清理间隔（秒）
        """
        if interval_seconds < 60:
            raise ValueError("清理间隔不能少于60秒")
        self._cleanup_interval = interval_seconds
    
    def _auto_cleanup_worker(self) -> None:
        """自动清理工作线程"""
        while not self._stop_cleanup.is_set():
            try:
                # 执行清理
                self.cleanup_expired_cache()
                
                # 等待下次清理
                if self._stop_cleanup.wait(timeout=self._cleanup_interval):
                    break  # 收到停止信号
                    
            except Exception as e:
                print(f"自动缓存清理出错: {e}")
                # 出错后等待较短时间再重试
                if self._stop_cleanup.wait(timeout=300):  # 5分钟后重试
                    break
    
    def force_cleanup(self) -> Dict[str, Any]:
        """
        强制执行缓存清理并返回统计信息
        
        Returns:
            清理统计信息
        """
        stats_before = self.get_cache_stats()
        self.cleanup_expired_cache()
        stats_after = self.get_cache_stats()
        
        return {
            'cleanup_time': datetime.now().isoformat(),
            'records_before': stats_before['total_records'],
            'records_after': stats_after['total_records'],
            'records_cleaned': stats_before['total_records'] - stats_after['total_records'],
            'expired_before': stats_before['expired_records']
        }
    
    def optimize_database(self) -> None:
        """优化数据库性能"""
        try:
            with self._get_connection() as conn:
                # 执行VACUUM以回收空间
                conn.execute("VACUUM")
                
                # 重建索引
                conn.execute("REINDEX")
                
                # 更新统计信息
                conn.execute("ANALYZE")
                
                conn.commit()
            
        except sqlite3.Error as e:
            raise CacheError(f"数据库优化失败: {e}")
    
    def get_cache_health(self) -> Dict[str, Any]:
        """
        获取缓存健康状态
        
        Returns:
            缓存健康状态信息
        """
        try:
            stats = self.get_cache_stats()
            
            # 计算健康指标
            total_records = stats['total_records']
            expired_records = stats['expired_records']
            active_records = stats['active_records']
            
            # 过期率
            expiry_rate = (expired_records / total_records * 100) if total_records > 0 else 0
            
            # 命中率估算（基于访问统计）
            avg_access = stats['access_stats']['average_access_count']
            hit_rate_estimate = min(avg_access * 10, 100) if avg_access > 0 else 0
            
            # 健康评分 (0-100)
            health_score = 100
            if expiry_rate > 50:  # 过期率过高
                health_score -= (expiry_rate - 50)
            if total_records > 10000:  # 记录数过多
                health_score -= min((total_records - 10000) / 1000 * 5, 30)
            
            health_score = max(0, health_score)
            
            # 健康状态
            if health_score >= 80:
                health_status = "excellent"
            elif health_score >= 60:
                health_status = "good"
            elif health_score >= 40:
                health_status = "fair"
            else:
                health_status = "poor"
            
            return {
                'health_score': round(health_score, 1),
                'health_status': health_status,
                'total_records': total_records,
                'active_records': active_records,
                'expired_records': expired_records,
                'expiry_rate_percent': round(expiry_rate, 1),
                'estimated_hit_rate_percent': round(hit_rate_estimate, 1),
                'recommendations': self._get_health_recommendations(health_score, expiry_rate, total_records)
            }
            
        except Exception as e:
            return {
                'health_score': 0,
                'health_status': 'error',
                'error': str(e)
            }
    
    def _get_health_recommendations(self, health_score: float, expiry_rate: float, total_records: int) -> list:
        """获取健康改善建议"""
        recommendations = []
        
        if expiry_rate > 50:
            recommendations.append("过期记录过多，建议增加清理频率")
        
        if total_records > 10000:
            recommendations.append("缓存记录过多，建议减少TTL或增加清理频率")
        
        if health_score < 60:
            recommendations.append("缓存健康状况不佳，建议执行数据库优化")
        
        if not recommendations:
            recommendations.append("缓存状态良好，无需特殊操作")
        
        return recommendations
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            包含缓存统计的字典
        """
        try:
            with self._get_connection() as conn:
                # 总记录数
                cursor = conn.execute("SELECT COUNT(*) as total FROM weather_cache")
                total_records = cursor.fetchone()['total']
                
                # 按类型统计
                cursor = conn.execute("""
                    SELECT data_type, COUNT(*) as count 
                    FROM weather_cache 
                    GROUP BY data_type
                """)
                type_stats = {row['data_type']: row['count'] for row in cursor.fetchall()}
                
                # 过期记录数
                now = datetime.now().isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) as expired 
                    FROM weather_cache 
                    WHERE expires_at < ?
                """, (now,))
                expired_records = cursor.fetchone()['expired']
                
                # 访问统计
                cursor = conn.execute("""
                    SELECT 
                        AVG(access_count) as avg_access,
                        MAX(access_count) as max_access,
                        SUM(access_count) as total_access
                    FROM weather_cache
                """)
                access_stats = cursor.fetchone()
                
                return {
                    'total_records': total_records,
                    'expired_records': expired_records,
                    'active_records': total_records - expired_records,
                    'type_distribution': type_stats,
                    'access_stats': {
                        'average_access_count': access_stats['avg_access'] or 0,
                        'max_access_count': access_stats['max_access'] or 0,
                        'total_accesses': access_stats['total_access'] or 0
                    }
                }
            
        except sqlite3.Error as e:
            raise CacheError(f"获取缓存统计失败: {e}")
    
    def clear_all_cache(self) -> None:
        """清空所有缓存"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM weather_cache")
                conn.commit()
            
        except sqlite3.Error as e:
            raise CacheError(f"清空缓存失败: {e}")
    
    def close(self) -> None:
        """关闭数据库连接"""
        # 停止自动清理
        self.stop_auto_cleanup()
        
        # 强制关闭任何可能的连接
        if hasattr(self, '_connection') and self._connection:
            try:
                self._connection.close()
            except:
                pass
        self._connection = None
        
        # 强制垃圾回收以释放SQLite连接
        import gc
        gc.collect()
    
    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()