"""
ReAct Agent 工具集合
包含基础工具和网络查询工具
"""
import os
import datetime
import logging
import re
import operator
import requests
import json
from typing import List, Dict
from langchain_core.tools import tool
from dotenv import load_dotenv
from src.agents.tools import get_current_time

# 加载环境变量
load_dotenv()

logger = logging.getLogger("resume-agent.react_tools")

# 安全的数学操作符
SAFE_OPERATORS = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
    '//': operator.floordiv,
    '%': operator.mod,
    '**': operator.pow,
    '^': operator.xor,
}

@tool
def calculate(expression: str) -> float:
    """
    执行数学表达式计算。
    
    支持的操作符：+、-、*、/、//、%、**、^
    支持括号和基本数学函数。
    
    参数:
    - expression: 数学表达式字符串，如 "2 + 3 * 4" 或 "(10 + 5) / 3"
    
    返回:
    - float: 计算结果
    """
    try:
        # 移除空格
        expression = expression.replace(' ', '')
        
        # 验证表达式只包含数字、操作符和括号
        if not re.match(r'^[0-9+\-*/().\s]+$', expression):
            raise ValueError("表达式包含不安全的字符")
        
        # 使用 eval 计算（已限制操作符）
        result = eval(expression, {"__builtins__": {}}, SAFE_OPERATORS)
        logger.info(f"[Tool Call] calculate({expression}) -> {result}")
        return float(result)
    except Exception as e:
        error_msg = f"计算失败: {str(e)}"
        logger.error(f"[Tool Call] calculate({expression}) -> {error_msg}")
        raise ValueError(error_msg)

@tool
def date_calculator(start_date: str, end_date: str = None, operation: str = "diff") -> str:
    """
    计算日期之间的差值或进行日期运算。
    
    参数:
    - start_date: 起始日期，格式 "YYYY-MM-DD" 或 "YYYY.MM"
    - end_date: 结束日期（可选），格式同上。如果为 None，使用当前日期
    - operation: 操作类型
        - "diff": 计算两个日期的差值（默认）
        - "add_days": 在起始日期上添加天数（需要 end_date 为天数）
        - "subtract_days": 从起始日期减去天数（需要 end_date 为天数）
    
    返回:
    - str: 计算结果，如 "4年0个月0天" 或 "2024-01-15"
    """
    try:
        # 解析日期
        def parse_date(date_str: str) -> datetime.datetime:
            if '.' in date_str:
                # 格式：YYYY.MM
                parts = date_str.split('.')
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 1
                return datetime.datetime(year, month, 1)
            elif '-' in date_str:
                # 格式：YYYY-MM-DD
                return datetime.datetime.strptime(date_str, "%Y-%m-%d")
            else:
                raise ValueError(f"不支持的日期格式: {date_str}")
        
        start = parse_date(start_date)
        
        if operation == "diff":
            if end_date is None:
                end = datetime.datetime.now()
            else:
                end = parse_date(end_date)
            
            # 计算差值
            delta = end - start
            years = delta.days // 365
            months = (delta.days % 365) // 30
            days = delta.days % 30
            
            result = f"{years}年{months}个月{days}天"
            logger.info(f"[Tool Call] date_calculator(start={start_date}, end={end_date}, op=diff) -> {result}")
            return result
        elif operation in ["add_days", "subtract_days"]:
            if end_date is None:
                raise ValueError("add_days 和 subtract_days 操作需要提供天数")
            days = int(end_date)
            if operation == "add_days":
                result_date = start + datetime.timedelta(days=days)
            else:
                result_date = start - datetime.timedelta(days=days)
            result = result_date.strftime("%Y-%m-%d")
            logger.info(f"[Tool Call] date_calculator(start={start_date}, days={days}, op={operation}) -> {result}")
            return result
        else:
            raise ValueError(f"不支持的操作: {operation}")
            
    except Exception as e:
        error_msg = f"日期计算失败: {str(e)}"
        logger.error(f"[Tool Call] date_calculator({start_date}, {end_date}, {operation}) -> {error_msg}")
        raise ValueError(error_msg)

@tool
async def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    网络搜索工具：搜索网络信息，返回参考网站信息。
    
    使用博查 API 进行网络搜索。
    
    参数:
    - query: 搜索查询字符串
    - max_results: 最大返回结果数（默认 5）
    
    返回:
    - List[Dict]: 搜索结果列表，每个结果包含：
        - title: 网站标题
        - url: 网站 URL
        - snippet: 内容摘要
        - source: 来源网站名称
    """
    try:
        logger.info(f"[Tool Call] web_search(query={query}, max_results={max_results})")
        
        # 获取 API key
        api_key = os.getenv("BOCHA_API_KEY")
        if not api_key:
            logger.error("[Tool Call] web_search -> BOCHA_API_KEY 未设置")
            raise ValueError("BOCHA_API_KEY 环境变量未设置")
        
        # 调用博查 API
        url = "https://api.bocha.cn/v1/web-search"
        
        payload = json.dumps({
            "query": query,
            "summary": True,
            "count": max_results
        })
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 发送请求
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        
        # 解析响应
        result_data = response.json()
        
        # 检查响应状态
        if result_data.get("code") != 200:
            error_msg = result_data.get("msg", "未知错误")
            logger.error(f"[Tool Call] web_search -> API 返回错误: {error_msg}")
            raise ValueError(f"搜索失败: {error_msg}")
        
        # 提取搜索结果
        web_pages = result_data.get("data", {}).get("webPages", {})
        search_results = web_pages.get("value", [])
        
        # 转换为工具需要的格式
        formatted_results = []
        for item in search_results[:max_results]:
            formatted_results.append({
                "title": item.get("name", "无标题"),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("siteName", item.get("displayUrl", "未知来源"))
            })
        
        logger.info(f"[Tool Call] web_search -> 返回 {len(formatted_results)} 个结果")
        
        # 详细记录每个搜索结果
        for idx, result in enumerate(formatted_results, 1):
            logger.info(f"[Tool Call] web_search 结果 #{idx}:")
            logger.info(f"  标题: {result.get('title', '无标题')}")
            logger.info(f"  URL: {result.get('url', '无URL')}")
            logger.info(f"  来源: {result.get('source', '未知')}")
            logger.info(f"  摘要: {result.get('snippet', '无摘要')}")
        
        # 记录完整 JSON 格式的结果（用于调试）
        logger.debug(f"[Tool Call] web_search 完整结果 JSON:\n{json.dumps(formatted_results, ensure_ascii=False, indent=2)}")
        
        return formatted_results
        
    except requests.exceptions.RequestException as e:
        error_msg = f"网络请求失败: {str(e)}"
        logger.error(f"[Tool Call] web_search -> {error_msg}")
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"搜索失败: {str(e)}"
        logger.error(f"[Tool Call] web_search -> {error_msg}")
        raise ValueError(error_msg)

# ReAct 工具列表
REACT_TOOLS = [
    get_current_time,
    calculate,
    date_calculator,
    web_search
]

