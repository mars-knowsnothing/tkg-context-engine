#!/usr/bin/env python3
"""
创建推理和派生事件的演示数据脚本
用于测试时间线界面的左右分布显示效果
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta

BASE_URL = 'http://localhost:8001'

# 推理和分析事件数据
INFERENCE_EVENTS = [
    {
        "name": "故障根因分析_DATABASE_CONNECTION_TIMEOUT",
        "type": "episode",
        "content": "根据监控数据和错误日志分析，数据库连接超时的根本原因是连接池配置不当，建议增加最大连接数至200",
        "properties": {
            "original_type": "RootCauseEvent",
            "source": "AI分析引擎",
            "category": "根因分析",
            "severity": "HIGH",
            "confidence": 0.85,
            "analysis_method": "correlation_analysis",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        }
    },
    {
        "name": "服务性能趋势预测_ittzp-auth-service",
        "type": "episode", 
        "content": "基于过去7天的性能数据预测，认证服务的响应时间在未来24小时内可能增长15%，建议提前扩容",
        "properties": {
            "original_type": "PredictionEvent",
            "source": "预测模型",
            "category": "性能预测",
            "severity": "MEDIUM",
            "confidence": 0.78,
            "prediction_window": "24h",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        }
    },
    {
        "name": "异常模式检测_错误率突增",
        "type": "episode",
        "content": "检测到认证服务在过去1小时内错误率异常突增，疑似与数据库连接问题相关，建议立即排查",
        "properties": {
            "original_type": "AnalysisResult", 
            "source": "异常检测算法",
            "category": "模式识别",
            "severity": "CRITICAL",
            "confidence": 0.92,
            "anomaly_type": "error_rate_spike",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat()
        }
    },
    {
        "name": "容量规划建议_数据库连接池",
        "type": "episode",
        "content": "根据负载分析和故障模式，推荐将数据库连接池参数调整为：最大连接数200，最小连接数50，连接超时30秒",
        "properties": {
            "original_type": "InferredEvent",
            "source": "容量规划系统",
            "category": "系统优化", 
            "severity": "MEDIUM",
            "confidence": 0.80,
            "recommendation_type": "capacity_planning",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        }
    },
    {
        "name": "服务依赖关系推理_故障影响面",
        "type": "episode",
        "content": "分析得出认证服务故障可能影响下游15个微服务，预估影响用户数约50000，建议优先修复",
        "properties": {
            "original_type": "InferredEvent",
            "source": "依赖分析引擎", 
            "category": "影响分析",
            "severity": "HIGH",
            "confidence": 0.88,
            "impact_scope": "downstream_services",
            "affected_users": 50000,
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        }
    },
    {
        "name": "自动修复建议_连接池重启",
        "type": "episode",
        "content": "基于故障模式匹配，建议执行数据库连接池重启操作，预计修复时间2分钟，成功率95%",
        "properties": {
            "original_type": "InferredEvent",
            "source": "自动修复引擎",
            "category": "修复建议",
            "severity": "HIGH", 
            "confidence": 0.95,
            "fix_type": "connection_pool_restart",
            "estimated_fix_time": "2min",
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        }
    }
]

async def create_inference_events():
    """创建推理和分析事件"""
    async with aiohttp.ClientSession() as session:
        created_count = 0
        failed_count = 0
        
        print("🧠 开始创建推理和分析事件...")
        
        for event_data in INFERENCE_EVENTS:
            try:
                async with session.post(
                    f"{BASE_URL}/api/knowledge/",
                    json=event_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        created_count += 1
                        print(f"✅ 创建推理事件: {event_data['name'][:50]}...")
                    else:
                        error_text = await response.text()
                        print(f"❌ 创建失败 ({response.status}): {event_data['name'][:50]}...")
                        print(f"   错误信息: {error_text[:100]}...")
                        failed_count += 1
                        
            except Exception as e:
                print(f"❌ 创建异常: {event_data['name'][:50]}...")
                print(f"   异常信息: {str(e)[:100]}...")
                failed_count += 1
                
        print(f"\n📊 推理事件创建统计:")
        print(f"   ✅ 成功创建: {created_count} 个事件")
        print(f"   ❌ 创建失败: {failed_count} 个事件")
        print(f"   📈 总计处理: {len(INFERENCE_EVENTS)} 个事件")
        
        # 验证创建结果
        print(f"\n🔍 验证推理事件...")
        try:
            async with session.post(
                f"{BASE_URL}/api/temporal/query",
                json={"query": "推理", "limit": 10},
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ 找到推理相关事件: {len(result['nodes'])} 个")
                    print(f"   查询结果: {result['explanation']}")
                else:
                    print(f"❌ 验证查询失败 ({response.status})")
        except Exception as e:
            print(f"❌ 验证查询异常: {str(e)}")
            
        return created_count, failed_count

async def main():
    """主函数"""
    print("🚀 推理事件创建工具启动")
    print("=" * 50)
    
    try:
        # 检查后端服务连接
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status != 200:
                    print(f"❌ 后端服务不可用 (状态码: {response.status})")
                    return
                print(f"✅ 后端服务连接正常")
        
        # 创建推理事件
        created, failed = await create_inference_events()
        
        print("\n" + "=" * 50)
        if failed == 0:
            print("🎉 所有推理事件创建完成！")
        else:
            print(f"⚠️  推理事件创建完成，但有 {failed} 个失败")
            
        print(f"\n💡 使用方法:")
        print(f"   1. 打开前端页面: http://localhost:3000 或 http://localhost:3002")
        print(f"   2. 进入 'Temporal Explorer' 页面")
        print(f"   3. 尝试查询: '分析', '推理', '预测', '建议' 等关键词")
        print(f"   4. 观察时间线左右分布效果")
        
    except Exception as e:
        print(f"❌ 程序执行异常: {e}")

if __name__ == "__main__":
    asyncio.run(main())