"""
命令解析器属性测试

使用基于属性的测试验证命令解析器的正确性。
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from weather_plugin.command_parser import CommandParser
from weather_plugin.models import CommandType, WeatherCommand


class TestCommandParserProperties:
    """命令解析器属性测试类"""
    
    def setup_method(self):
        """设置测试方法"""
        self.parser = CommandParser()
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_parse_command_never_crashes(self, input_text):
        """
        属性10：自然语言命令解析 - 解析器永不崩溃
        **验证需求：6.1, 6.3**
        
        对于任何输入文本，命令解析器都不应该崩溃
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        try:
            result = self.parser.parse_command(input_text)
            # 如果返回结果，应该是 WeatherCommand 对象或 None
            assert result is None or isinstance(result, WeatherCommand)
        except Exception as e:
            pytest.fail(f"解析器在输入 '{input_text}' 时崩溃: {e}")
    
    @given(st.sampled_from([
        "天气 北京", "weather Beijing", "今天北京天气怎么样", 
        "What's the weather like in Shanghai?", "北京的天气"
    ]))
    @settings(max_examples=100)
    def test_weather_queries_return_current_weather_command(self, weather_query):
        """
        属性10：自然语言命令解析 - 天气查询识别
        **验证需求：6.1, 6.3**
        
        对于明确的天气查询，应该返回当前天气命令类型
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(weather_query)
        
        assert result is not None, f"天气查询 '{weather_query}' 应该被识别"
        assert result.command_type == CommandType.CURRENT_WEATHER, \
            f"天气查询 '{weather_query}' 应该返回当前天气命令类型"
    
    @given(st.sampled_from([
        "预报 上海", "forecast Shanghai", "明天深圳天气", 
        "tomorrow's weather in Beijing", "上海的预报"
    ]))
    @settings(max_examples=100)
    def test_forecast_queries_return_forecast_command(self, forecast_query):
        """
        属性10：自然语言命令解析 - 预报查询识别
        **验证需求：6.1, 6.3**
        
        对于明确的预报查询，应该返回预报命令类型
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(forecast_query)
        
        assert result is not None, f"预报查询 '{forecast_query}' 应该被识别"
        assert result.command_type == CommandType.FORECAST, \
            f"预报查询 '{forecast_query}' 应该返回预报命令类型"
    
    @given(st.sampled_from([
        "帮助", "help", "使用说明", "天气帮助", "weather help"
    ]))
    @settings(max_examples=100)
    def test_help_queries_return_help_command(self, help_query):
        """
        属性10：自然语言命令解析 - 帮助查询识别
        **验证需求：6.1, 6.3**
        
        对于帮助查询，应该返回帮助命令类型
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(help_query)
        
        assert result is not None, f"帮助查询 '{help_query}' 应该被识别"
        assert result.command_type == CommandType.HELP, \
            f"帮助查询 '{help_query}' 应该返回帮助命令类型"
    
    @given(st.sampled_from([
        "天气 北京", "weather Beijing", "预报 上海", "forecast Shanghai",
        "今天北京天气怎么样", "明天上海天气", "What's the weather in Tokyo?"
    ]))
    @settings(max_examples=100)
    def test_location_extraction_consistency(self, query_with_location):
        """
        属性10：自然语言命令解析 - 位置提取一致性
        **验证需求：6.1, 6.3**
        
        对于包含位置的查询，应该能够提取出位置信息
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(query_with_location)
        
        if result is not None:
            # 如果解析成功，应该包含位置信息
            assert result.location is not None and len(result.location.strip()) > 0, \
                f"查询 '{query_with_location}' 应该包含位置信息，但得到: {result.location}"
    
    @given(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs')), 
                   min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_extract_location_robustness(self, text):
        """
        属性10：自然语言命令解析 - 位置提取鲁棒性
        **验证需求：6.1, 6.3**
        
        位置提取方法对于任何文本输入都不应该崩溃
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        try:
            location = self.parser.extract_location(text)
            # 如果返回位置，应该是字符串或None
            assert location is None or isinstance(location, str)
            # 如果返回位置，不应该为空字符串
            if location is not None:
                assert len(location.strip()) > 0
        except Exception as e:
            pytest.fail(f"位置提取在输入 '{text}' 时崩溃: {e}")
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_detect_command_type_robustness(self, text):
        """
        属性10：自然语言命令解析 - 命令类型检测鲁棒性
        **验证需求：6.1, 6.3**
        
        命令类型检测对于任何文本输入都不应该崩溃，并且总是返回有效的命令类型
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        try:
            command_type = self.parser.detect_command_type(text)
            # 应该总是返回有效的CommandType
            assert isinstance(command_type, CommandType)
        except Exception as e:
            pytest.fail(f"命令类型检测在输入 '{text}' 时崩溃: {e}")
    
    @given(st.sampled_from([
        ("设置位置 北京", CommandType.SET_LOCATION, "北京"),
        ("set location Beijing", CommandType.SET_LOCATION, "Beijing"),
        ("默认位置 上海", CommandType.SET_LOCATION, "上海"),
        ("设置单位 摄氏度", CommandType.SET_UNITS, None),
        ("set units metric", CommandType.SET_UNITS, None),
    ]))
    @settings(max_examples=100)
    def test_configuration_commands_parsing(self, test_case):
        """
        属性10：自然语言命令解析 - 配置命令解析
        **验证需求：6.1, 6.3**
        
        配置相关的命令应该被正确解析
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        query, expected_type, expected_location = test_case
        result = self.parser.parse_command(query)
        
        assert result is not None, f"配置命令 '{query}' 应该被识别"
        assert result.command_type == expected_type, \
            f"配置命令 '{query}' 应该返回 {expected_type}，但得到 {result.command_type}"
        
        if expected_location is not None:
            assert result.location == expected_location, \
                f"配置命令 '{query}' 应该提取位置 '{expected_location}'，但得到 '{result.location}'"
    
    @given(st.text(min_size=0, max_size=10).filter(lambda x: not x.strip()))
    @settings(max_examples=100)
    def test_empty_input_handling(self, empty_text):
        """
        属性10：自然语言命令解析 - 空输入处理
        **验证需求：6.1, 6.3**
        
        对于空输入或只包含空白字符的输入，应该返回None
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(empty_text)
        assert result is None, f"空输入 '{empty_text}' 应该返回None，但得到 {result}"
    
    @given(st.sampled_from([
        "小时预报 成都", "hourly forecast Chengdu", "成都的小时预报"
    ]))
    @settings(max_examples=100)
    def test_hourly_forecast_parsing(self, hourly_query):
        """
        属性10：自然语言命令解析 - 小时预报解析
        **验证需求：6.1, 6.3**
        
        小时预报查询应该被正确识别
        """
        # Feature: smart-weather-assistant, Property 10: 自然语言命令解析
        result = self.parser.parse_command(hourly_query)
        
        assert result is not None, f"小时预报查询 '{hourly_query}' 应该被识别"
        assert result.command_type == CommandType.HOURLY_FORECAST, \
            f"小时预报查询 '{hourly_query}' 应该返回小时预报命令类型"
        assert result.location is not None, \
            f"小时预报查询 '{hourly_query}' 应该包含位置信息"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])