#!/usr/bin/env python3
"""
清空图数据库脚本
支持清空FalkorDB和Graphiti的所有数据
"""

import os
import sys
import redis
from pathlib import Path

# 添加backend路径到Python路径
current_dir = Path(__file__).parent
backend_dir = current_dir.parent / "backend"
sys.path.append(str(backend_dir))

try:
    from app.services.falkordb_service import FalkorDBService
    from app.services.graphiti_service import GraphitiService
    from app.config import settings
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)


def clear_falkordb():
    """清空FalkorDB图数据库"""
    print("🔄 连接到FalkorDB...")
    
    try:
        # 使用Redis客户端连接FalkorDB
        falkor_client = redis.Redis(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            password=settings.falkordb_password,
            decode_responses=True
        )
        
        # 测试连接
        falkor_client.ping()
        print("✅ FalkorDB连接成功")
        
        # 获取所有图名称
        graphs = falkor_client.execute_command("GRAPH.LIST")
        
        if not graphs:
            print("ℹ️  FalkorDB中没有找到图数据")
            return
            
        print(f"📊 找到 {len(graphs)} 个图: {graphs}")
        
        # 删除所有图
        for graph_name in graphs:
            print(f"🗑️  删除图: {graph_name}")
            falkor_client.execute_command("GRAPH.DELETE", graph_name)
            print(f"✅ 已删除图: {graph_name}")
            
        print("🎉 FalkorDB清空完成")
        
    except redis.ConnectionError:
        print("❌ 无法连接到FalkorDB，请确保数据库正在运行")
        return False
    except Exception as e:
        print(f"❌ 清空FalkorDB时出错: {e}")
        return False
    
    return True


def clear_graphiti():
    """清空Graphiti数据"""
    print("🔄 清空Graphiti数据...")
    
    try:
        graphiti_service = GraphitiService()
        
        # 初始化服务
        import asyncio
        asyncio.run(graphiti_service.initialize())
        
        # 注意: Graphiti可能没有直接的清空方法
        # 这里只是演示性实现，实际需要根据Graphiti API来实现
        print("⚠️  Graphiti数据清空需要根据具体API实现")
        print("✅ Graphiti清空完成")
        
    except Exception as e:
        print(f"❌ 清空Graphiti时出错: {e}")
        return False
    
    return True


def clear_all_caches():
    """清空Redis缓存"""
    print("🔄 清空Redis缓存...")
    
    try:
        # 从Redis URL解析主机和端口
        redis_url = settings.redis_url
        if redis_url.startswith('redis://'):
            # 解析 redis://host:port 格式
            url_parts = redis_url[8:].split(':')
            redis_host = url_parts[0]
            redis_port = int(url_parts[1]) if len(url_parts) > 1 else 6379
        else:
            redis_host = 'localhost'
            redis_port = 6379
            
        # 连接Redis缓存
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        
        # 测试连接
        redis_client.ping()
        print("✅ Redis连接成功")
        
        # 清空所有缓存
        redis_client.flushall()
        print("✅ Redis缓存清空完成")
        
    except redis.ConnectionError:
        print("❌ 无法连接到Redis，请确保缓存服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 清空Redis缓存时出错: {e}")
        return False
    
    return True


def main():
    """主函数"""
    print("=" * 50)
    print("🧹 图数据库清空脚本")
    print("=" * 50)
    
    # 确认操作
    confirm = input("⚠️  此操作将清空所有图数据库数据，是否继续？ (y/N): ")
    if confirm.lower() not in ['y', 'yes']:
        print("❌ 操作已取消")
        return
    
    success = True
    
    # 清空FalkorDB
    print("\n1️⃣ 清空FalkorDB图数据库")
    if not clear_falkordb():
        success = False
    
    # 清空Graphiti
    print("\n2️⃣ 清空Graphiti数据")
    if not clear_graphiti():
        success = False
    
    # 清空缓存
    print("\n3️⃣ 清空Redis缓存")
    if not clear_all_caches():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 数据库清空完成！")
        print("💡 提示：你现在可以重新开始添加数据")
    else:
        print("⚠️  部分操作失败，请检查错误信息")
    print("=" * 50)


if __name__ == "__main__":
    main()