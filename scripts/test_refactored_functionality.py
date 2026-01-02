#!/usr/bin/env python3
"""
测试重构后的功能 - 验证两种 agent 类型和 SSE 流式输出
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Optional, Dict, List
import httpx
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置
API_BASE_URL = "http://localhost:8000"
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
    print_colored(f"\n{'='*70}", Colors.CYAN)
    print_colored(f"  {message}", Colors.BOLD + Colors.CYAN)
    print_colored(f"{'='*70}\n", Colors.CYAN)


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


async def test_stream_endpoint(
    action: str,
    session_id: str = "test_session",
    agent_type: str = "planner_worker",
    **kwargs
) -> Dict:
    """
    测试统一的 /stream 端点
    
    Args:
        action: 操作类型 (chat, generate, history, reasoning_status, token_stats, token_summary)
        session_id: 会话ID
        agent_type: agent类型 (planner_worker, dual_track)
        **kwargs: 其他参数
    
    Returns:
        dict: 测试结果
    """
    result = {
        "action": action,
        "agent_type": agent_type,
        "session_id": session_id,
        "success": False,
        "error": None,
        "events": [],
        "event_types": {},
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration": None
    }
    
    # 构建请求体
    request_body = {
        "action": action,
        "session_id": session_id,
        "agent_type": agent_type,
        **kwargs
    }
    
    print_info(f"发送请求: {json.dumps(request_body, ensure_ascii=False, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{API_BASE_URL}/stream",
                json=request_body,
                headers={"Accept": "text/event-stream"}
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    result["error"] = f"HTTP {response.status_code}: {error_text.decode()}"
                    print_error(f"请求失败: {result['error']}")
                    return result
                
                print_success(f"开始接收 SSE 流 (状态码: {response.status_code})")
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # 解析 SSE 格式: data: {...}
                    if line.startswith("data: "):
                        try:
                            data_str = line[6:]  # 移除 "data: " 前缀
                            event_data = json.loads(data_str)
                            
                            event_type = event_data.get("type", "unknown")
                            result["events"].append(event_data)
                            
                            # 统计事件类型
                            result["event_types"][event_type] = result["event_types"].get(event_type, 0) + 1
                            
                            # 显示事件
                            if event_type == "status":
                                print_info(f"[状态] {event_data.get('content', '')}")
                            elif event_type == "partial":
                                content = event_data.get("content", "")
                                if len(content) > 100:
                                    content = content[:100] + "..."
                                print_colored(f"[部分] {content}", Colors.MAGENTA)
                            elif event_type == "final":
                                print_success(f"[完成] {event_data.get('content', '')[:100]}...")
                            elif event_type == "error":
                                print_error(f"[错误] {event_data.get('content', '')}")
                            
                        except json.JSONDecodeError as e:
                            print_warning(f"无法解析 SSE 数据: {line[:100]}... (错误: {e})")
                        except Exception as e:
                            print_warning(f"处理 SSE 事件时出错: {e}")
                    
                    elif line.startswith("event: "):
                        # 处理 event: 行（如果有）
                        event_name = line[7:].strip()
                        print_info(f"收到事件类型: {event_name}")
                    
                    elif line.startswith(":"):
                        # 注释行，忽略
                        continue
                
                result["success"] = True
                result["end_time"] = datetime.now().isoformat()
                if result["start_time"]:
                    start = datetime.fromisoformat(result["start_time"])
                    end = datetime.fromisoformat(result["end_time"])
                    result["duration"] = (end - start).total_seconds()
                
                print_success(f"✓ 测试完成 (耗时: {result['duration']:.2f}秒)")
                print_info(f"收到事件统计: {json.dumps(result['event_types'], ensure_ascii=False, indent=2)}")
                
    except httpx.TimeoutException:
        result["error"] = f"请求超时 (>{TIMEOUT}秒)"
        print_error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        print_error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    return result


async def run_all_tests():
    """运行所有测试"""
    print_header("开始测试重构后的功能")
    
    # 检查服务器
    print_info("检查服务器状态...")
    if not await check_server_health():
        print_error("服务器未运行，请先执行: make dev")
        return False
    
    print_success("服务器运行正常")
    
    # 生成唯一的会话ID
    base_session_id = f"test_{int(time.time())}"
    
    all_results = []
    
    # 测试 1: planner_worker chat
    print_header("测试 1: planner_worker - chat")
    result1 = await test_stream_endpoint(
        action="chat",
        session_id=f"{base_session_id}_pw",
        agent_type="planner_worker",
        message="你好，我是张三，36岁，毕业于北京大学计算机科学专业"
    )
    all_results.append(result1)
    await asyncio.sleep(2)  # 等待一下
    
    # 测试 2: dual_track chat
    print_header("测试 2: dual_track - chat")
    result2 = await test_stream_endpoint(
        action="chat",
        session_id=f"{base_session_id}_dt",
        agent_type="dual_track",
        message="你好，我是李四，30岁，有5年软件工程师经验"
    )
    all_results.append(result2)
    await asyncio.sleep(2)
    
    # 测试 3: history (使用 planner_worker 的会话)
    print_header("测试 3: history - 获取会话历史")
    result3 = await test_stream_endpoint(
        action="history",
        session_id=f"{base_session_id}_pw",
        agent_type="planner_worker",
        limit=10
    )
    all_results.append(result3)
    await asyncio.sleep(1)
    
    # 测试 4: token_stats
    print_header("测试 4: token_stats - 获取token统计")
    result4 = await test_stream_endpoint(
        action="token_stats",
        session_id=f"{base_session_id}_pw",
        agent_type="planner_worker"
    )
    all_results.append(result4)
    await asyncio.sleep(1)
    
    # 测试 5: reasoning_status (dual_track 特有)
    print_header("测试 5: reasoning_status - 获取推理状态 (dual_track)")
    result5 = await test_stream_endpoint(
        action="reasoning_status",
        session_id=f"{base_session_id}_dt",
        agent_type="dual_track"
    )
    all_results.append(result5)
    await asyncio.sleep(1)
    
    # 汇总结果
    print_header("测试结果汇总")
    
    success_count = sum(1 for r in all_results if r["success"])
    total_count = len(all_results)
    
    print_info(f"总测试数: {total_count}")
    print_success(f"成功: {success_count}")
    print_error(f"失败: {total_count - success_count}")
    
    for i, result in enumerate(all_results, 1):
        status = "✓" if result["success"] else "✗"
        color = Colors.GREEN if result["success"] else Colors.RED
        print_colored(
            f"{status} 测试 {i}: {result['action']} ({result['agent_type']}) - "
            f"{'成功' if result['success'] else '失败'}",
            color
        )
        if result.get("error"):
            print_error(f"  错误: {result['error']}")
        if result.get("duration"):
            print_info(f"  耗时: {result['duration']:.2f}秒")
        if result.get("event_types"):
            print_info(f"  事件: {json.dumps(result['event_types'], ensure_ascii=False)}")
    
    # 保存结果
    output_file = f"scripts/test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print_info(f"\n完整结果已保存到: {output_file}")
    
    return success_count == total_count


async def main():
    """主函数"""
    try:
        success = await run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_warning("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

