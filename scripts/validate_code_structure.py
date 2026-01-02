#!/usr/bin/env python3
"""
代码结构验证脚本 - 检查重构后的代码结构是否正确
不需要运行服务器，只检查导入和基本结构
"""
import sys
import importlib
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_import(module_name: str, description: str) -> tuple[bool, str]:
    """检查模块导入"""
    try:
        importlib.import_module(module_name)
        return True, f"✓ {description}"
    except ImportError as e:
        return False, f"✗ {description}: {e}"
    except Exception as e:
        return False, f"✗ {description}: 意外错误 - {e}"

def check_class_in_module(module_name: str, class_name: str, description: str) -> tuple[bool, str]:
    """检查模块中是否存在指定的类"""
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, class_name):
            return True, f"✓ {description}"
        else:
            return False, f"✗ {description}: 类 {class_name} 不存在"
    except Exception as e:
        return False, f"✗ {description}: {e}"

def main():
    """主函数"""
    print("=" * 70)
    print("  代码结构验证")
    print("=" * 70)
    print()
    
    results = []
    
    # 检查核心模块
    print("检查核心模块...")
    print("-" * 70)
    
    checks = [
        ("src.schema", "Schema 模块"),
        ("src.schema.request", "Request Schema"),
        ("src.schema.response", "Response Schema"),
        ("src.schema.session", "Session Schema"),
        ("src.service", "Service 模块"),
        ("src.service.session_service", "Session Service"),
        ("src.service.planner_worker_service", "Planner Worker Service"),
        ("src.service.dual_track_service", "Dual Track Service"),
        ("src.service.token_statistics_service", "Token Statistics Service"),
        ("src.api.routes", "API Routes"),
        ("src.config.settings", "Settings Config"),
    ]
    
    for module_name, description in checks:
        success, message = check_import(module_name, description)
        results.append((success, message))
        print(message)
    
    print()
    
    # 检查关键类
    print("检查关键类...")
    print("-" * 70)
    
    class_checks = [
        ("src.schema.request", "StreamRequest", "StreamRequest 类"),
        ("src.schema.session", "AgentType", "AgentType 枚举"),
        ("src.service.session_service", "SessionService", "SessionService 类"),
        ("src.service.planner_worker_service", "PlannerWorkerService", "PlannerWorkerService 类"),
        ("src.service.dual_track_service", "DualTrackService", "DualTrackService 类"),
    ]
    
    for module_name, class_name, description in class_checks:
        success, message = check_class_in_module(module_name, class_name, description)
        results.append((success, message))
        print(message)
    
    print()
    
    # 检查 API 路由
    print("检查 API 路由...")
    print("-" * 70)
    
    try:
        from src.api import routes
        router = routes.api_router
        
        # 检查路由是否存在
        routes_found = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes_found.append(f"{list(route.methods)[0]} {route.path}")
        
        print(f"✓ 找到 {len(routes_found)} 个路由:")
        for route in routes_found:
            print(f"  - {route}")
        
        # 检查是否有 /stream 路由
        has_stream = any("/stream" in route for route in routes_found)
        if has_stream:
            print("✓ /stream 路由存在")
            results.append((True, "✓ /stream 路由"))
        else:
            print("✗ /stream 路由不存在")
            results.append((False, "✗ /stream 路由"))
            
    except Exception as e:
        print(f"✗ 检查 API 路由失败: {e}")
        results.append((False, f"✗ API 路由检查: {e}"))
    
    print()
    
    # 汇总结果
    print("=" * 70)
    print("  验证结果汇总")
    print("=" * 70)
    
    success_count = sum(1 for success, _ in results if success)
    total_count = len(results)
    
    print(f"\n总检查项: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    
    if success_count == total_count:
        print("\n✓ 所有检查通过！代码结构正确。")
        return 0
    else:
        print("\n✗ 部分检查失败，请查看上面的错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

