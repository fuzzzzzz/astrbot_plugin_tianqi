"""
帮助系统和命令建议

提供帮助信息、命令示例和模糊命令处理功能。
"""

import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from .models import CommandType
from .localization import localization_manager


class HelpSystem:
    """帮助系统和命令建议器"""
    
    def __init__(self):
        """初始化帮助系统"""
        self._init_command_examples()
        self._init_fuzzy_matching()
    
    def _init_command_examples(self):
        """初始化命令示例"""
        self.command_examples = {
            CommandType.CURRENT_WEATHER: [
                "天气 北京",
                "今天北京天气怎么样",
                "北京的天气",
                "weather Beijing",
                "What's the weather like in Shanghai?",
                "/weather 上海"
            ],
            CommandType.FORECAST: [
                "预报 广州",
                "明天深圳天气",
                "广州的预报",
                "forecast Guangzhou",
                "Tomorrow's weather in Shenzhen",
                "/forecast 杭州"
            ],
            CommandType.HOURLY_FORECAST: [
                "小时预报 成都",
                "成都的小时预报",
                "hourly forecast Chengdu",
                "hourly weather for Wuhan"
            ],
            CommandType.SET_LOCATION: [
                "设置位置 北京",
                "默认位置 上海",
                "set location Beijing",
                "set my default location to Shanghai"
            ],
            CommandType.SET_UNITS: [
                "设置单位 摄氏度",
                "使用公制单位",
                "set units metric",
                "use fahrenheit"
            ],
            CommandType.ALERTS: [
                "天气警报 北京",
                "北京的警报",
                "weather alerts for Beijing",
                "notifications for Shanghai"
            ],
            CommandType.ACTIVITIES: [
                "活动推荐 上海",
                "上海适合什么活动",
                "what can I do in Beijing",
                "outdoor activities for Guangzhou"
            ],
            CommandType.HELP: [
                "帮助",
                "help",
                "使用说明",
                "天气帮助",
                "weather help"
            ]
        }
    
    def _init_fuzzy_matching(self):
        """初始化模糊匹配"""
        # 常见的命令关键词
        self.command_keywords = {
            'weather': ['天气', 'weather', '气温', '温度'],
            'forecast': ['预报', 'forecast', '明天', 'tomorrow', '后天'],
            'hourly': ['小时', 'hourly', '每小时'],
            'help': ['帮助', 'help', '使用', 'usage', '命令', 'command'],
            'set': ['设置', 'set', '配置', 'config'],
            'location': ['位置', 'location', '地点', 'place'],
            'units': ['单位', 'units', '度数', 'temperature'],
            'alerts': ['警报', 'alert', '通知', 'notification', '提醒'],
            'activities': ['活动', 'activity', '推荐', 'recommend']
        }
        
        # 常见的拼写错误和变体
        self.common_typos = {
            'weather': ['wether', 'wheather', 'weater', '天气', 'tianqi'],
            'forecast': ['forcast', 'forceast', '预报', 'yubao'],
            'help': ['halp', 'hlep', '帮助', 'bangzhu'],
            'location': ['loaction', 'locaton', '位置', 'weizhi'],
            'beijing': ['bejing', 'peking', '北京'],
            'shanghai': ['shangai', '上海'],
            'guangzhou': ['canton', '广州'],
            'shenzhen': ['shenzen', '深圳']
        }
    
    def get_help_message(self, command_type: Optional[CommandType] = None) -> str:
        """
        获取帮助信息
        
        Args:
            command_type: 特定命令类型，如果为None则返回通用帮助
            
        Returns:
            str: 帮助信息
        """
        if command_type:
            return self._get_specific_help(command_type)
        else:
            return self._get_general_help()
    
    def _get_general_help(self) -> str:
        """获取通用帮助信息"""
        return localization_manager.format_message('help')
    
    def _get_specific_help(self, command_type: CommandType) -> str:
        """获取特定命令的帮助信息"""
        examples = self.command_examples.get(command_type, [])
        
        if command_type == CommandType.CURRENT_WEATHER:
            return self._format_command_help(
                "当前天气查询",
                "查询指定位置的当前天气信息",
                examples
            )
        elif command_type == CommandType.FORECAST:
            return self._format_command_help(
                "天气预报查询",
                "查询指定位置的天气预报信息",
                examples
            )
        elif command_type == CommandType.HOURLY_FORECAST:
            return self._format_command_help(
                "小时预报查询",
                "查询指定位置的小时天气预报",
                examples
            )
        elif command_type == CommandType.SET_LOCATION:
            return self._format_command_help(
                "设置默认位置",
                "设置您的默认查询位置",
                examples
            )
        elif command_type == CommandType.SET_UNITS:
            return self._format_command_help(
                "设置温度单位",
                "设置温度显示单位（摄氏度/华氏度）",
                examples
            )
        elif command_type == CommandType.ALERTS:
            return self._format_command_help(
                "天气警报",
                "查询和管理天气警报通知",
                examples
            )
        elif command_type == CommandType.ACTIVITIES:
            return self._format_command_help(
                "活动推荐",
                "根据天气条件推荐适合的活动",
                examples
            )
        else:
            return self._get_general_help()
    
    def _format_command_help(self, title: str, description: str, examples: List[str]) -> str:
        """格式化命令帮助信息"""
        help_text = f"📋 {title}\n\n"
        help_text += f"📝 {description}\n\n"
        
        if examples:
            help_text += "💡 使用示例:\n"
            for i, example in enumerate(examples[:5], 1):  # 最多显示5个示例
                help_text += f"  {i}. {example}\n"
        
        return help_text.strip()
    
    def suggest_command(self, invalid_input: str) -> Optional[str]:
        """
        为无效输入建议命令
        
        Args:
            invalid_input: 无效的用户输入
            
        Returns:
            Optional[str]: 建议的命令，如果没有合适建议则返回None
        """
        if not invalid_input or not invalid_input.strip():
            return None
        
        input_lower = invalid_input.lower().strip()
        
        # 尝试模糊匹配命令关键词
        best_match = self._find_best_keyword_match(input_lower)
        if best_match:
            return self._generate_suggestion_message(best_match, invalid_input)
        
        # 尝试拼写纠正
        corrected = self._suggest_spelling_correction(input_lower)
        if corrected:
            return f"您是否想要查询: {corrected}？"
        
        # 如果包含地名，建议天气查询
        if self._contains_location(input_lower):
            return "您是否想要查询天气？请尝试: 天气 [地点名称]"
        
        return None
    
    def _find_best_keyword_match(self, input_text: str) -> Optional[Tuple[str, float]]:
        """查找最佳关键词匹配"""
        best_match = None
        best_score = 0.0
        
        for category, keywords in self.command_keywords.items():
            for keyword in keywords:
                # 计算相似度
                similarity = SequenceMatcher(None, input_text, keyword.lower()).ratio()
                
                # 检查是否包含关键词
                if keyword.lower() in input_text:
                    similarity = max(similarity, 0.8)
                
                # 检查部分匹配
                if any(word in input_text for word in keyword.lower().split()):
                    similarity = max(similarity, 0.6)
                
                if similarity > best_score and similarity > 0.5:
                    best_score = similarity
                    best_match = (category, similarity)
        
        return best_match
    
    def _generate_suggestion_message(self, match_info: Tuple[str, float], original_input: str) -> str:
        """生成建议消息"""
        category, score = match_info
        
        if category == 'weather':
            return "您是否想要查询天气？请尝试:\n• 天气 [地点]\n• [地点]的天气怎么样"
        elif category == 'forecast':
            return "您是否想要查询预报？请尝试:\n• 预报 [地点]\n• 明天[地点]天气"
        elif category == 'help':
            return "您是否需要帮助？请尝试:\n• 帮助\n• help\n• 使用说明"
        elif category == 'set':
            return "您是否想要设置配置？请尝试:\n• 设置位置 [地点]\n• 设置单位 摄氏度"
        elif category == 'location':
            return "您是否想要设置位置？请尝试:\n• 设置位置 [地点名称]\n• 默认位置 [地点名称]"
        elif category == 'alerts':
            return "您是否想要查询警报？请尝试:\n• 天气警报 [地点]\n• [地点]的警报"
        elif category == 'activities':
            return "您是否想要活动推荐？请尝试:\n• 活动推荐 [地点]\n• [地点]适合什么活动"
        else:
            return "请尝试使用以下格式:\n• 天气 [地点]\n• 预报 [地点]\n• 帮助"
    
    def _suggest_spelling_correction(self, input_text: str) -> Optional[str]:
        """建议拼写纠正"""
        words = input_text.split()
        corrected_words = []
        has_correction = False
        
        for word in words:
            best_correction = None
            best_score = 0.0
            
            # 检查所有已知的拼写错误
            for correct_word, typos in self.common_typos.items():
                for typo in typos:
                    similarity = SequenceMatcher(None, word.lower(), typo.lower()).ratio()
                    if similarity > best_score and similarity > 0.7:
                        best_score = similarity
                        best_correction = correct_word
            
            if best_correction:
                corrected_words.append(best_correction)
                has_correction = True
            else:
                corrected_words.append(word)
        
        if has_correction:
            return ' '.join(corrected_words)
        
        return None
    
    def _contains_location(self, text: str) -> bool:
        """检查文本是否包含地名"""
        # 常见城市名称
        cities = [
            '北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '西安', '重庆',
            'beijing', 'shanghai', 'guangzhou', 'shenzhen', 'hangzhou', 'nanjing',
            'wuhan', 'chengdu', 'xian', 'chongqing', 'london', 'paris', 'tokyo',
            'new york', 'los angeles', 'chicago', 'houston'
        ]
        
        # 地名指示词
        location_indicators = ['市', '省', '县', '区', '镇', '村', '州', '港', '岛', 'city', 'state']
        
        text_lower = text.lower()
        
        # 检查是否包含已知城市
        if any(city in text_lower for city in cities):
            return True
        
        # 检查是否包含地名指示词
        if any(indicator in text for indicator in location_indicators):
            return True
        
        return False
    
    def get_command_examples(self, command_type: CommandType, count: int = 3) -> List[str]:
        """
        获取命令示例
        
        Args:
            command_type: 命令类型
            count: 返回示例数量
            
        Returns:
            List[str]: 命令示例列表
        """
        examples = self.command_examples.get(command_type, [])
        return examples[:count]
    
    def get_all_commands_summary(self) -> str:
        """获取所有命令的简要说明"""
        summary = "🌤️ 天气助手可用命令:\n\n"
        
        command_descriptions = {
            CommandType.CURRENT_WEATHER: "🌡️ 当前天气 - 查询实时天气信息",
            CommandType.FORECAST: "📅 天气预报 - 查询未来天气预报",
            CommandType.HOURLY_FORECAST: "⏰ 小时预报 - 查询小时级天气预报",
            CommandType.SET_LOCATION: "📍 设置位置 - 设置默认查询位置",
            CommandType.SET_UNITS: "🌡️ 设置单位 - 设置温度显示单位",
            CommandType.ALERTS: "⚠️ 天气警报 - 查询天气警报信息",
            CommandType.ACTIVITIES: "🎯 活动推荐 - 获取天气相关活动建议",
            CommandType.HELP: "❓ 帮助信息 - 显示详细使用说明"
        }
        
        for cmd_type, description in command_descriptions.items():
            summary += f"• {description}\n"
        
        summary += "\n💡 提示: 您可以使用自然语言询问，如 '北京今天天气怎么样？'"
        
        return summary
    
    def is_help_request(self, text: str) -> bool:
        """判断是否为帮助请求"""
        help_keywords = [
            '帮助', 'help', '使用说明', '命令', 'command', 'usage',
            '怎么用', 'how to use', '说明', 'instruction'
        ]
        
        text_lower = text.lower().strip()
        return any(keyword in text_lower for keyword in help_keywords)


# 全局帮助系统实例
help_system = HelpSystem()