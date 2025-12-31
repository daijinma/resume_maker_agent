#!/usr/bin/env python3
"""
自动测试脚本 - 测试第一句话的完整流程
发送消息并监控响应，自动排查错误
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Optional
import httpx
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置
API_BASE_URL = "http://localhost:8000"
TEST_MESSAGE = "你好我是张三，过完年正好36啦，毕业于北京大学计算机科学本科"
SESSION_ID = f"test_session_{int(time.time())}"
TIMEOUT = 300  # 5分钟超时


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_colored(message: str, color: str = Colors.WHITE):
    """打印彩色消息"""
    print(f"{color}{message}{Colors.RESET}")


def print_header(message: str):
    """打印标题"""
    print_colored(f"\n{'='*60}", Colors.CYAN)
    print_colored(f"  {message}", Colors.BOLD + Colors.CYAN)
    print_colored(f"{'='*60}\n", Colors.CYAN)


def print_success(message: str):
    """打印成功消息"""
    print_colored(f"✓ {message}", Colors.GREEN)


def print_error(message: str):
    """打印错误消息"""
    print_colored(f"✗ {message}", Colors.RED)


def print_warning(message: str):
    """打印警告消息"""
    print_colored(f"⚠ {message}", Colors.YELLOW)


def print_info(message: str):
    """打印信息消息"""
    print_colored(f"ℹ {message}", Colors.BLUE)


async def check_server_health() -> bool:
    """检查服务器是否运行"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/")
            return response.status_code == 200
    except Exception as e:
        print_error(f"无法连接到服务器 {API_BASE_URL}: {e}")
        return False


async def send_message_and_monitor(
    message: str,
    session_id: str,
    agent_type: str = "planner_worker"
) -> dict:
    """
    发送消息并监控SSE流式响应
    
    Returns:
        dict: 包含完整响应信息的字典
    """
    result = {
        "success": False,
        "error": None,
        "events": [],
        "final_response": None,
        "status_messages": [],
        "tool_calls": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration": None
    }
    
    url = f"{API_BASE_URL}/stream"
    payload = {
        "action": "chat",
        "message": message,
        "session_id": session_id,
        "agent_type": agent_type
    }
    
    print_info(f"发送请求到: {url}")
    print_info(f"Session ID: {session_id}")
    print_info(f"Agent Type: {agent_type}")
    print_info(f"消息内容: {message}\n")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", url, json=payload) as response:
                print_info(f"HTTP状态码: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    result["error"] = f"HTTP {response.status_code}: {error_text.decode()}"
                    print_error(result["error"])
                    return result
                
                print_success("连接成功，开始接收流式响应...\n")
                
                buffer = ""
                event_count = 0
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # SSE格式: data: {...}
                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        try:
                            event_data = json.loads(data_str)
                            event_count += 1
                            
                            event_type = event_data.get("type", "unknown")
                            content = event_data.get("content", "")
                            debug_info = event_data.get("debug", {})
                            
                            # 记录事件
                            event_record = {
                                "type": event_type,
                                "content": content,
                                "debug": debug_info,
                                "timestamp": datetime.now().isoformat()
                            }
                            result["events"].append(event_record)
                            
                            # 根据事件类型处理
                            if event_type == "status":
                                result["status_messages"].append(content)
                                print_colored(f"[状态] {content}", Colors.CYAN)
                                
                            elif event_type == "error":
                                result["error"] = content
                                print_error(f"[错误] {content}")
                                
                            elif event_type == "final":
                                result["final_response"] = event_data
                                result["success"] = True
                                print_success(f"\n[最终响应]")
                                print_colored(f"  内容: {content}", Colors.GREEN)
                                
                                if "pending_questions" in event_data:
                                    questions = event_data.get("pending_questions", [])
                                    if questions:
                                        print_info(f"  待回答问题: {len(questions)} 个")
                                        for q in questions:
                                            print_colored(f"    - {q}", Colors.YELLOW)
                                
                                if "debug" in event_data:
                                    debug = event_data["debug"]
                                    print_info(f"  调试信息: {json.dumps(debug, indent=2, ensure_ascii=False)}")
                                
                            else:
                                print_colored(f"[{event_type}] {content}", Colors.WHITE)
                            
                            # 检查工具调用
                            if "tool" in content.lower() or "调用" in content:
                                result["tool_calls"].append(content)
                        
                        except json.JSONDecodeError as e:
                            print_warning(f"JSON解析失败: {data_str[:100]}...")
                            print_warning(f"错误: {e}")
                    
                    elif line.startswith("event: "):
                        # SSE事件类型
                        event_name = line[7:]
                        print_info(f"事件类型: {event_name}")
                    
                    elif line.startswith(":"):
                        # SSE注释，忽略
                        continue
                    
                    else:
                        # 其他格式，记录原始内容
                        print_warning(f"未识别的SSE格式: {line[:100]}")
                
                result["end_time"] = datetime.now().isoformat()
                start = datetime.fromisoformat(result["start_time"])
                end = datetime.fromisoformat(result["end_time"])
                result["duration"] = (end - start).total_seconds()
                
                print_info(f"\n总共接收到 {event_count} 个事件")
                print_info(f"总耗时: {result['duration']:.2f} 秒")
                
    except httpx.TimeoutException:
        result["error"] = f"请求超时（{TIMEOUT}秒）"
        result["end_time"] = datetime.now().isoformat()
        print_error(result["error"])
        
    except Exception as e:
        result["error"] = f"请求失败: {str(e)}"
        result["end_time"] = datetime.now().isoformat()
        print_error(result["error"])
        import traceback
        print_error(f"详细错误:\n{traceback.format_exc()}")
    
    return result


def analyze_result(result: dict) -> bool:
    """分析结果并排查问题"""
    print_header("结果分析")
    
    success = result.get("success", False)
    error = result.get("error")
    events = result.get("events", [])
    final_response = result.get("final_response")
    
    if success and final_response:
        print_success("✓ 请求成功完成")
        print_info(f"  收到 {len(events)} 个事件")
        print_info(f"  状态消息: {len(result.get('status_messages', []))} 条")
        print_info(f"  工具调用: {len(result.get('tool_calls', []))} 次")
        return True
    
    if error:
        print_error(f"✗ 请求失败: {error}")
        print_header("错误排查")
        
        # 检查常见问题
        if "连接" in error.lower() or "connection" in error.lower():
            print_warning("可能的问题: 服务器未启动")
            print_info("解决方案: 运行 'make dev' 启动服务器")
        
        elif "timeout" in error.lower() or "超时" in error.lower():
            print_warning("可能的问题: 请求处理时间过长")
            print_info("解决方案: 检查服务器日志，查看是否有卡住的请求")
        
        elif "HTTP" in error:
            print_warning("可能的问题: API接口错误")
            print_info("解决方案: 检查路由配置和请求格式")
        
        # 显示事件历史
        if events:
            print_info(f"\n已接收的事件 ({len(events)} 个):")
            for i, event in enumerate(events[:10], 1):  # 只显示前10个
                print_colored(f"  {i}. [{event['type']}] {event['content'][:100]}", Colors.WHITE)
            if len(events) > 10:
                print_info(f"  ... 还有 {len(events) - 10} 个事件")
    
    else:
        print_warning("⚠ 请求未完成，但没有明确的错误信息")
        print_info(f"  收到 {len(events)} 个事件")
        if events:
            print_info("最后几个事件:")
            for event in events[-5:]:
                print_colored(f"  [{event['type']}] {event['content'][:100]}", Colors.WHITE)
    
    return False


def save_result(result: dict, output_file: Optional[str] = None):
    """保存结果到文件"""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = project_root / "scripts" / f"test_result_{timestamp}.json"
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print_info(f"\n结果已保存到: {output_path}")


async def main():
    """主函数"""
    print_header("自动测试脚本 - 第一句话测试")
    
    # 1. 检查服务器
    print_info("步骤 1: 检查服务器状态...")
    if not await check_server_health():
        print_error("服务器未运行，请先启动服务器: make dev")
        sys.exit(1)
    print_success("服务器运行正常")
    
    # 2. 发送消息并监控
    print_info("\n步骤 2: 发送测试消息...")
    result = await send_message_and_monitor(
        message=TEST_MESSAGE,
        session_id=SESSION_ID,
        agent_type="planner_worker"
    )
    
    # 3. 分析结果
    success = analyze_result(result)
    
    # 4. 保存结果
    save_result(result)
    
    # 5. 总结
    print_header("测试总结")
    if success:
        print_success("✓ 测试通过！第一句话处理成功")
        sys.exit(0)
    else:
        print_error("✗ 测试失败！请查看上面的错误信息")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("\n\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print_error(f"\n\n未预期的错误: {e}")
        import traceback
        print_error(traceback.format_exc())
        sys.exit(1)

