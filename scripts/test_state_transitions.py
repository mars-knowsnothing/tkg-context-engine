#!/usr/bin/env python3
# 动态状态转换机制测试脚本

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.temporal_graphiti_service import TemporalGraphitiService
from app.models.temporal_schemas import TemporalEventType, TemporalValidityState

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_state_transition_mechanism():
    """测试动态状态转换机制"""
    service = TemporalGraphitiService()
    
    try:
        logger.info("🚀 Initializing TemporalGraphitiService...")
        await service.initialize()
        
        logger.info("✅ Service initialized successfully")
        
        # 创建测试故障事件
        logger.info("📝 Creating test fault event...")
        fault_event_data = {
            'name': 'Database Connection Timeout Fault',
            'description': 'Database connection pool exhausted causing timeouts',
            'event_type': 'fault_occurrence',
            'category': 'database_fault',
            'source_system': 'db_monitor',
            'occurrence_time': datetime.now(timezone.utc).isoformat(),
            'validity_start': datetime.now(timezone.utc).isoformat(),
            'custom_properties': {
                'service_name': 'user-api',
                'severity': 'high',
                'error_rate': 0.08,  # 8% 错误率，会触发阈值超出条件
                'incident_id': 'INC-2025-001'
            }
        }
        
        fault_event_id = await service.create_temporal_event(fault_event_data)
        logger.info(f"✅ Created fault event: {fault_event_id}")
        
        # 等待初始状态转换处理
        await asyncio.sleep(2)
        
        # 检查事件生命周期
        logger.info("🔍 Checking initial event lifecycle...")
        lifecycle = await service.get_event_lifecycle(fault_event_id)
        if lifecycle:
            logger.info(f"Current state: {lifecycle['current_state']}")
            logger.info(f"State transitions: {len(lifecycle['state_transitions'])}")
        
        # 模拟错误率超阈值触发状态转换
        logger.info("⚡ Triggering threshold exceeded condition...")
        transition_result = await service.trigger_event_state_transition(
            fault_event_id,
            {
                'error_rate': 0.12,  # 12% 错误率，超过阈值
                'threshold_type': 'error_rate_threshold_exceeded'
            }
        )
        logger.info(f"Transition result: {transition_result}")
        
        # 等待状态转换处理
        await asyncio.sleep(1)
        
        # 创建恢复事件
        logger.info("🔧 Creating recovery event...")
        recovery_event_data = {
            'name': 'Database Connection Pool Restart',
            'description': 'Restarting connection pool to resolve timeout issues',
            'event_type': 'recovery_process',
            'category': 'service_recovery',
            'source_system': 'user-api',
            'occurrence_time': (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            'validity_start': (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
            'custom_properties': {
                'recovery_action': 'connection_pool_restart',
                'target_service': 'user-api',
                'operator': 'sre_team'
            }
        }
        
        recovery_event_id = await service.create_temporal_event(recovery_event_data)
        logger.info(f"✅ Created recovery event: {recovery_event_id}")
        
        # 等待一段时间让自动监控运行
        logger.info("⏰ Waiting for automated monitoring to run...")
        await asyncio.sleep(5)
        
        # 模拟服务恢复完成
        logger.info("✅ Triggering service restored condition...")
        service_restored_result = await service.trigger_event_state_transition(
            fault_event_id,
            {
                'service_restored': True,
                'recovery_confirmation': True,
                'metrics_normalized': True
            }
        )
        logger.info(f"Service restored result: {service_restored_result}")
        
        # 手动状态变更测试
        logger.info("👤 Testing manual state change...")
        manual_result = await service.manual_state_change(
            recovery_event_id,
            target_state='invalid',
            reason='Recovery action completed successfully',
            operator='test_operator'
        )
        logger.info(f"Manual state change result: {manual_result}")
        
        # 获取最终状态统计
        logger.info("📊 Getting transition statistics...")
        stats = await service.get_transition_statistics()
        logger.info(f"Total transitions: {stats['transition_engine']['total_transitions']}")
        logger.info(f"Automatic transitions: {stats['transition_engine']['automatic_transitions']}")
        logger.info(f"Manual transitions: {stats['transition_engine']['manual_transitions']}")
        
        # 获取最终的事件生命周期
        logger.info("📋 Final event lifecycle analysis...")
        final_fault_lifecycle = await service.get_event_lifecycle(fault_event_id)
        if final_fault_lifecycle:
            logger.info(f"Final fault state: {final_fault_lifecycle['current_state']}")
            logger.info(f"Total transitions: {final_fault_lifecycle['lifecycle_analysis']['total_transitions']}")
            logger.info(f"Duration: {final_fault_lifecycle['lifecycle_analysis']['duration_seconds']} seconds")
        
        final_recovery_lifecycle = await service.get_event_lifecycle(recovery_event_id)
        if final_recovery_lifecycle:
            logger.info(f"Final recovery state: {final_recovery_lifecycle['current_state']}")
        
        logger.info("🎉 State transition mechanism test completed successfully!")
        
        return {
            'fault_event_id': fault_event_id,
            'recovery_event_id': recovery_event_id,
            'statistics': stats,
            'fault_lifecycle': final_fault_lifecycle,
            'recovery_lifecycle': final_recovery_lifecycle
        }
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        await service.close()

async def main():
    """主函数"""
    logger.info("🔬 Starting Dynamic State Transition Mechanism Test")
    
    try:
        test_results = await test_state_transition_mechanism()
        
        logger.info("\n" + "="*60)
        logger.info("📋 TEST RESULTS SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Fault Event ID: {test_results['fault_event_id']}")
        logger.info(f"✅ Recovery Event ID: {test_results['recovery_event_id']}")
        logger.info(f"📊 Total Transitions: {test_results['statistics']['transition_engine']['total_transitions']}")
        logger.info(f"🤖 Automatic Transitions: {test_results['statistics']['transition_engine']['automatic_transitions']}")
        logger.info(f"👤 Manual Transitions: {test_results['statistics']['transition_engine']['manual_transitions']}")
        
        if test_results['fault_lifecycle']:
            duration = test_results['fault_lifecycle']['lifecycle_analysis']['duration_seconds']
            logger.info(f"⏱️  Event Lifecycle Duration: {duration} seconds")
        
        logger.info("="*60)
        logger.info("🎉 ALL TESTS PASSED!")
        
    except Exception as e:
        logger.error(f"💥 Tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())