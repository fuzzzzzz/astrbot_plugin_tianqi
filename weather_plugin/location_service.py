"""
位置服务实现

提供位置解析、验证和拼写纠错功能。
"""

import re
import asyncio
import aiohttp
from typing import List, Optional, Dict, Any, Tuple
from difflib import get_close_matches
from .interfaces import ILocationService
from .models import LocationInfo, Coordinates, LocationError
from .config import WeatherConfig


class LocationService(ILocationService):
    """位置服务实现"""
    
    def __init__(self, config: WeatherConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 常见城市数据库（简化版）
        self.known_cities = {
            # 中国主要城市
            "北京": {"country": "CN", "region": "北京市", "coords": (39.9042, 116.4074)},
            "上海": {"country": "CN", "region": "上海市", "coords": (31.2304, 121.4737)},
            "广州": {"country": "CN", "region": "广东省", "coords": (23.1291, 113.2644)},
            "深圳": {"country": "CN", "region": "广东省", "coords": (22.5431, 114.0579)},
            "杭州": {"country": "CN", "region": "浙江省", "coords": (30.2741, 120.1551)},
            "南京": {"country": "CN", "region": "江苏省", "coords": (32.0603, 118.7969)},
            "武汉": {"country": "CN", "region": "湖北省", "coords": (30.5928, 114.3055)},
            "成都": {"country": "CN", "region": "四川省", "coords": (30.5728, 104.0668)},
            "西安": {"country": "CN", "region": "陕西省", "coords": (34.3416, 108.9398)},
            "重庆": {"country": "CN", "region": "重庆市", "coords": (29.5630, 106.5516)},
            
            # 国际主要城市
            "london": {"country": "GB", "region": "England", "coords": (51.5074, -0.1278)},
            "paris": {"country": "FR", "region": "Île-de-France", "coords": (48.8566, 2.3522)},
            "tokyo": {"country": "JP", "region": "Tokyo", "coords": (35.6762, 139.6503)},
            "new york": {"country": "US", "region": "New York", "coords": (40.7128, -74.0060)},
            "los angeles": {"country": "US", "region": "California", "coords": (34.0522, -118.2437)},
            "sydney": {"country": "AU", "region": "New South Wales", "coords": (-33.8688, 151.2093)},
            "moscow": {"country": "RU", "region": "Moscow", "coords": (55.7558, 37.6176)},
            "berlin": {"country": "DE", "region": "Berlin", "coords": (52.5200, 13.4050)},
        }
        
        # 城市别名映射
        self.city_aliases = {
            "bj": "北京",
            "beijing": "北京",
            "sh": "上海",
            "shanghai": "上海",
            "gz": "广州",
            "guangzhou": "广州",
            "sz": "深圳",
            "shenzhen": "深圳",
            "hz": "杭州",
            "hangzhou": "杭州",
            "nj": "南京",
            "nanjing": "南京",
            "wh": "武汉",
            "wuhan": "武汉",
            "cd": "成都",
            "chengdu": "成都",
            "xa": "西安",
            "xian": "西安",
            "cq": "重庆",
            "chongqing": "重庆",
            
            # 英文别名
            "nyc": "new york",
            "la": "los angeles",
            "sf": "san francisco",
            "dc": "washington",
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保 HTTP 会话已创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def parse_location(self, location_input: str) -> LocationInfo:
        """解析位置输入"""
        if not location_input or not location_input.strip():
            raise LocationError("位置输入不能为空")
        
        location_input = location_input.strip()
        
        # 尝试解析坐标格式 (lat,lon) 或 (lat, lon)
        coord_match = self._parse_coordinates_string(location_input)
        if coord_match:
            lat, lon = coord_match
            if self.validate_coordinates(lat, lon):
                return LocationInfo(
                    name=f"{lat:.4f},{lon:.4f}",
                    coordinates=Coordinates(lat, lon)
                )
            else:
                raise LocationError(f"无效的坐标: {lat}, {lon}")
        
        # 标准化位置名称
        normalized_location = self._normalize_location_name(location_input)
        
        # 检查别名映射
        if normalized_location.lower() in self.city_aliases:
            normalized_location = self.city_aliases[normalized_location.lower()]
        
        # 检查已知城市
        city_info = self._get_known_city_info(normalized_location)
        if city_info:
            lat, lon = city_info["coords"]
            return LocationInfo(
                name=normalized_location,
                coordinates=Coordinates(lat, lon),
                country=city_info["country"],
                region=city_info["region"]
            )
        
        # 如果不是已知城市，返回基本信息（需要后续地理编码）
        return LocationInfo(name=normalized_location)
    
    def _parse_coordinates_string(self, location_input: str) -> Optional[Tuple[float, float]]:
        """解析坐标字符串"""
        # 匹配格式: "lat,lon" 或 "lat, lon" 或 "(lat,lon)" 或 "(lat, lon)"
        coord_patterns = [
            r'^\s*\(?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\)?\s*$',
            r'^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*$'
        ]
        
        for pattern in coord_patterns:
            match = re.match(pattern, location_input)
            if match:
                try:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    return (lat, lon)
                except ValueError:
                    continue
        
        return None
    
    def _normalize_location_name(self, location: str) -> str:
        """标准化位置名称"""
        # 移除多余空格和特殊字符
        location = re.sub(r'\s+', ' ', location.strip())
        
        # 移除常见的后缀词
        suffixes_to_remove = ['市', '省', '县', '区', '镇', 'city', 'province', 'county']
        for suffix in suffixes_to_remove:
            if location.endswith(suffix):
                location = location[:-len(suffix)].strip()
        
        return location
    
    def _get_known_city_info(self, location: str) -> Optional[Dict[str, Any]]:
        """获取已知城市信息"""
        # 精确匹配
        if location in self.known_cities:
            return self.known_cities[location]
        
        # 不区分大小写匹配
        location_lower = location.lower()
        for city, info in self.known_cities.items():
            if city.lower() == location_lower:
                return info
        
        return None
    
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """验证坐标有效性"""
        try:
            # 检查纬度范围
            if not (-90 <= lat <= 90):
                return False
            
            # 检查经度范围
            if not (-180 <= lon <= 180):
                return False
            
            # 检查是否为有效数字
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                return False
            
            return True
            
        except (TypeError, ValueError):
            return False
    
    def suggest_corrections(self, invalid_location: str) -> List[str]:
        """建议位置拼写纠正"""
        if not invalid_location:
            return []
        
        invalid_location = invalid_location.strip().lower()
        
        # 获取所有可能的城市名称（包括别名）
        all_locations = list(self.known_cities.keys()) + list(self.city_aliases.keys())
        
        # 使用 difflib 进行模糊匹配
        suggestions = get_close_matches(
            invalid_location, 
            [loc.lower() for loc in all_locations],
            n=5,  # 最多返回5个建议
            cutoff=0.6  # 相似度阈值
        )
        
        # 转换回原始格式并去重
        result = []
        for suggestion in suggestions:
            # 找到原始格式的城市名
            for loc in all_locations:
                if loc.lower() == suggestion:
                    # 如果是别名，转换为实际城市名
                    if loc in self.city_aliases:
                        actual_city = self.city_aliases[loc]
                        if actual_city not in result:
                            result.append(actual_city)
                    else:
                        if loc not in result:
                            result.append(loc)
                    break
        
        return result
    
    async def geocode_location(self, location: str) -> Optional[Coordinates]:
        """地理编码位置"""
        try:
            # 首先尝试从已知城市获取坐标
            location_info = self.parse_location(location)
            if location_info.coordinates:
                return location_info.coordinates
            
            # 如果没有坐标，尝试使用在线地理编码服务
            return await self._online_geocode(location)
            
        except LocationError:
            return None
    
    async def _online_geocode(self, location: str) -> Optional[Coordinates]:
        """在线地理编码（使用 OpenStreetMap Nominatim API）"""
        try:
            await self._ensure_session()
            
            # 使用免费的 Nominatim API
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': location,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': f'{self.config.plugin_name}/{self.config.plugin_version}'
            }
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        result = data[0]
                        lat = float(result['lat'])
                        lon = float(result['lon'])
                        
                        if self.validate_coordinates(lat, lon):
                            return Coordinates(lat, lon)
                
                return None
                
        except Exception:
            # 如果在线地理编码失败，返回 None
            return None
    
    def get_location_display_name(self, location_info: LocationInfo) -> str:
        """获取位置的显示名称"""
        if location_info.region and location_info.country:
            return f"{location_info.name}, {location_info.region}, {location_info.country}"
        elif location_info.country:
            return f"{location_info.name}, {location_info.country}"
        else:
            return location_info.name
    
    def is_coordinates_format(self, location_input: str) -> bool:
        """检查输入是否为坐标格式"""
        return self._parse_coordinates_string(location_input) is not None
    
    def get_nearby_cities(self, coordinates: Coordinates, radius_km: float = 50) -> List[str]:
        """获取附近的城市（基于已知城市数据库）"""
        nearby_cities = []
        
        for city, info in self.known_cities.items():
            city_lat, city_lon = info["coords"]
            distance = self._calculate_distance(
                coordinates.latitude, coordinates.longitude,
                city_lat, city_lon
            )
            
            if distance <= radius_km:
                nearby_cities.append(city)
        
        return nearby_cities
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间的距离（简化的球面距离公式）"""
        import math
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # 使用 Haversine 公式
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（公里）
        earth_radius = 6371
        
        return earth_radius * c


class MockLocationService(ILocationService):
    """模拟位置服务（用于测试）"""
    
    def __init__(self, config: WeatherConfig):
        self.config = config
    
    def parse_location(self, location_input: str) -> LocationInfo:
        """解析位置输入（模拟）"""
        if not location_input or not location_input.strip():
            raise LocationError("位置输入不能为空")
        
        location_input = location_input.strip()
        
        # 模拟坐标解析
        if ',' in location_input:
            try:
                parts = location_input.split(',')
                if len(parts) == 2:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    if self.validate_coordinates(lat, lon):
                        return LocationInfo(
                            name=f"{lat:.4f},{lon:.4f}",
                            coordinates=Coordinates(lat, lon)
                        )
            except ValueError:
                pass
        
        # 模拟城市解析
        return LocationInfo(
            name=location_input,
            coordinates=Coordinates(39.9042, 116.4074),  # 默认北京坐标
            country="CN",
            region="模拟区域"
        )
    
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """验证坐标有效性（模拟）"""
        return -90 <= lat <= 90 and -180 <= lon <= 180
    
    def suggest_corrections(self, invalid_location: str) -> List[str]:
        """建议位置拼写纠正（模拟）"""
        return ["北京", "上海", "广州"]
    
    async def geocode_location(self, location: str) -> Optional[Coordinates]:
        """地理编码位置（模拟）"""
        return Coordinates(39.9042, 116.4074)  # 默认返回北京坐标