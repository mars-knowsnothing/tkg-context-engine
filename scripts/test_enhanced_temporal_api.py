#!/usr/bin/env python3
# 增强时序API端点测试脚本

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TemporalAPITester:
    """增强时序API测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """发送API请求"""
        url = f"{self.base_url}/api/temporal{endpoint}"
        
        try:
            if method.upper() == "GET":
                async with self.session.get(url) as response:
                    result = await response.json()
                    return {'status': response.status, 'data': result}
            elif method.upper() == "POST":
                async with self.session.post(url, json=data) as response:
                    result = await response.json()
                    return {'status': response.status, 'data': result}
            elif method.upper() == "PUT":
                async with self.session.put(url, json=data) as response:
                    result = await response.json()
                    return {'status': response.status, 'data': result}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {'status': 500, 'error': str(e)}
    
    async def test_health_check(self) -> bool:
        """测试健康检查端点"""
        logger.info("📡 Testing enhanced health check...")
        
        response = await self.make_request("GET", "/health/enhanced")
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        self.test_results.append({
            'test': 'enhanced_health_check',
            'success': success,
            'details': response
        })
        
        if success:
            logger.info("✅ Enhanced health check passed")
        else:
            logger.error(f"❌ Enhanced health check failed: {response}")
            
        return success
    
    async def test_create_temporal_event(self) -> str:
        """测试创建时序事件"""
        logger.info("📝 Testing temporal event creation...")
        
        event_data = {
            "name": "API Test Fault Event",
            "description": "Test fault event created via API",
            "event_type": "fault_occurrence",
            "category": "api_test",
            "source_system": "test_system",
            "severity": "high",
            "priority": 8,
            "tags": ["test", "fault", "api"],
            "custom_properties": {
                "service_name": "test-service",
                "error_rate": 0.25,
                "test_id": "api_test_001"
            }
        }
        
        response = await self.make_request("POST", "/events", event_data)
        
        success = response['status'] == 200 and response['data'].get('success', False)
        event_id = None
        
        if success:
            event_id = response['data']['data']['event_id']
            logger.info(f"✅ Created temporal event: {event_id}")
        else:
            logger.error(f"❌ Failed to create temporal event: {response}")
        
        self.test_results.append({
            'test': 'create_temporal_event',
            'success': success,
            'event_id': event_id,
            'details': response
        })
        
        return event_id
    
    async def test_get_temporal_event(self, event_id: str) -> bool:
        """测试获取时序事件"""
        logger.info(f"🔍 Testing get temporal event: {event_id}")
        
        response = await self.make_request("GET", f"/events/{event_id}")
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            event_data = response['data']['data']
            logger.info(f"✅ Retrieved event: {event_data['event']['name']}")
        else:
            logger.error(f"❌ Failed to get temporal event: {response}")
        
        self.test_results.append({
            'test': 'get_temporal_event',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_manual_state_change(self, event_id: str) -> bool:
        """测试手动状态变更"""
        logger.info(f"👤 Testing manual state change: {event_id}")
        
        state_change_data = {
            "target_state": "valid",
            "reason": "Confirmed by API test",
            "operator": "test_operator"
        }
        
        response = await self.make_request("PUT", f"/events/{event_id}/state", state_change_data)
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            logger.info(f"✅ State changed to: {state_change_data['target_state']}")
        else:
            logger.error(f"❌ Failed to change state: {response}")
        
        self.test_results.append({
            'test': 'manual_state_change',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_trigger_state_transition(self, event_id: str) -> bool:
        """测试触发状态转换"""
        logger.info(f"⚡ Testing state transition trigger: {event_id}")
        
        transition_data = {
            "trigger_data": {
                "error_rate": 0.3,
                "threshold_exceeded": True,
                "automated_check": True
            },
            "reason": "API test triggered transition"
        }
        
        response = await self.make_request("POST", f"/events/{event_id}/transition", transition_data)
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            result = response['data']['data']
            logger.info(f"✅ Transition triggered: {result.get('transition_results', [])}")
        else:
            logger.error(f"❌ Failed to trigger transition: {response}")
        
        self.test_results.append({
            'test': 'trigger_state_transition',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_get_event_lifecycle(self, event_id: str) -> bool:
        """测试获取事件生命周期"""
        logger.info(f"🔄 Testing get event lifecycle: {event_id}")
        
        response = await self.make_request("GET", f"/events/{event_id}/lifecycle")
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            lifecycle = response['data']['data']
            transitions_count = len(lifecycle.get('state_transitions', []))
            logger.info(f"✅ Retrieved lifecycle with {transitions_count} transitions")
        else:
            logger.error(f"❌ Failed to get lifecycle: {response}")
        
        self.test_results.append({
            'test': 'get_event_lifecycle',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_time_point_query(self) -> bool:
        """测试时点查询"""
        logger.info("⏰ Testing time point query...")
        
        query_data = {
            "query_time": datetime.now(timezone.utc).isoformat(),
            "event_types": ["fault_occurrence"],
            "categories": ["api_test"],
            "states": ["valid"],
            "include_transitions": True
        }
        
        response = await self.make_request("POST", "/query/time-point", query_data)
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            result = response['data']['data']
            events_count = result.get('count', 0)
            logger.info(f"✅ Time point query returned {events_count} events")
        else:
            logger.error(f"❌ Failed time point query: {response}")
        
        self.test_results.append({
            'test': 'time_point_query',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_time_range_query(self) -> bool:
        """测试时间范围查询"""
        logger.info("📅 Testing time range query...")
        
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(hours=1)).isoformat()
        end_time = now.isoformat()
        
        query_data = {
            "start_time": start_time,
            "end_time": end_time,
            "event_types": ["fault_occurrence"],
            "categories": ["api_test"],
            "include_lifecycle": True
        }
        
        response = await self.make_request("POST", "/query/time-range", query_data)
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            result = response['data']['data']
            transitions_count = result.get('count', 0)
            logger.info(f"✅ Time range query returned {transitions_count} transitions")
        else:
            logger.error(f"❌ Failed time range query: {response}")
        
        self.test_results.append({
            'test': 'time_range_query',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_enhanced_statistics(self) -> bool:
        """测试增强统计信息"""
        logger.info("📊 Testing enhanced statistics...")
        
        response = await self.make_request("GET", "/statistics/enhanced")
        
        success = response['status'] == 200 and response['data'].get('success', False)
        
        if success:
            stats = response['data']['data']
            total_transitions = stats.get('transition_engine', {}).get('total_transitions', 0)
            total_rules = stats.get('invalidation_engine', {}).get('total_rules', 0)
            logger.info(f"✅ Statistics: {total_transitions} transitions, {total_rules} rules")
        else:
            logger.error(f"❌ Failed to get enhanced statistics: {response}")
        
        self.test_results.append({
            'test': 'enhanced_statistics',
            'success': success,
            'details': response
        })
        
        return success
    
    async def test_legacy_compatibility(self) -> bool:
        """测试与旧API的兼容性"""
        logger.info("🔗 Testing legacy API compatibility...")
        
        # 测试原有的时序查询端点
        legacy_query_data = {
            "query": "API Test",
            "limit": 10,
            "at_time": datetime.now(timezone.utc).isoformat()
        }
        
        # 使用原有端点
        url = f"{self.base_url}/api/temporal/query"
        
        try:
            async with self.session.post(url, json=legacy_query_data) as response:
                result = await response.json()
                success = response.status == 200
        except Exception as e:
            success = False
            result = {'error': str(e)}
        
        if success:
            nodes_count = len(result.get('nodes', []))
            logger.info(f"✅ Legacy API returned {nodes_count} nodes")
        else:
            logger.error(f"❌ Legacy API compatibility failed: {result}")
        
        self.test_results.append({
            'test': 'legacy_compatibility',
            'success': success,
            'details': result
        })
        
        return success
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """运行完整的API测试套件"""
        logger.info("🚀 Starting comprehensive temporal API tests...")
        
        # 1. 健康检查
        await self.test_health_check()
        
        # 2. 创建时序事件
        event_id = await self.test_create_temporal_event()
        
        if event_id:
            # 3. 获取事件
            await self.test_get_temporal_event(event_id)
            
            # 4. 手动状态变更
            await self.test_manual_state_change(event_id)
            
            # 5. 触发状态转换
            await self.test_trigger_state_transition(event_id)
            
            # 6. 获取生命周期
            await self.test_get_event_lifecycle(event_id)
        
        # 7. 时点查询
        await self.test_time_point_query()
        
        # 8. 时间范围查询
        await self.test_time_range_query()
        
        # 9. 增强统计信息
        await self.test_enhanced_statistics()
        
        # 10. 遗留兼容性
        await self.test_legacy_compatibility()
        
        # 汇总测试结果
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result['success'])
        
        summary = {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'failed_tests': total_tests - successful_tests,
            'success_rate': (successful_tests / total_tests * 100) if total_tests > 0 else 0,
            'test_results': self.test_results,
            'created_event_id': event_id
        }
        
        return summary

async def main():
    """主函数"""
    logger.info("🔬 Starting Enhanced Temporal API Test Suite")
    
    async with TemporalAPITester() as tester:
        try:
            # 运行完整测试套件
            results = await tester.run_comprehensive_test()
            
            # 输出测试结果
            logger.info("\n" + "="*80)
            logger.info("📋 ENHANCED TEMPORAL API TEST RESULTS")
            logger.info("="*80)
            logger.info(f"✅ Total Tests: {results['total_tests']}")
            logger.info(f"✅ Successful: {results['successful_tests']}")
            logger.info(f"❌ Failed: {results['failed_tests']}")
            logger.info(f"📊 Success Rate: {results['success_rate']:.1f}%")
            
            if results['created_event_id']:
                logger.info(f"🆔 Created Event ID: {results['created_event_id']}")
            
            # 详细失败信息
            failed_tests = [r for r in results['test_results'] if not r['success']]
            if failed_tests:
                logger.info(f"\n❌ Failed Tests Details:")
                for failed_test in failed_tests:
                    logger.info(f"  • {failed_test['test']}: {failed_test.get('details', {}).get('error', 'Unknown error')}")
            
            logger.info("="*80)
            
            if results['success_rate'] >= 80:
                logger.info("🎉 ENHANCED TEMPORAL API TESTS MOSTLY PASSED!")
            else:
                logger.warning("⚠️  Some temporal API tests failed. Check the details above.")
            
            # 保存详细结果到文件
            with open('temporal_api_test_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            logger.info("📄 Detailed results saved to temporal_api_test_results.json")
            
        except Exception as e:
            logger.error(f"💥 Test suite failed with error: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())