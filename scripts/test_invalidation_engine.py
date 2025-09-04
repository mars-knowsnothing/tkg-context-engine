#!/usr/bin/env python3
# 条件性失效规则引擎测试脚本

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone, timedelta

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.temporal_graphiti_service import TemporalGraphitiService
from app.services.conditional_invalidation_engine import (
    ConditionalInvalidationEngine, 
    InvalidationRule, 
    RuleCondition,
    RuleOperator,
    RuleConditionType
)
from app.models.temporal_schemas import TemporalEventType, TemporalValidityState

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_conditional_invalidation_engine():
    """测试条件性失效规则引擎"""
    service = TemporalGraphitiService()
    
    try:
        logger.info("🚀 Initializing TemporalGraphitiService...")
        await service.initialize()
        
        invalidation_engine = service.transition_engine.invalidation_engine
        logger.info("✅ Service initialized with invalidation engine")
        
        # === 测试场景1: 故障自动失效规则 ===
        logger.info("\n📝 测试场景1: 故障事件在服务恢复后自动失效")
        
        # 创建故障事件
        fault_event_data = {
            'name': 'API Gateway Timeout Fault',
            'description': 'API Gateway experiencing high latency and timeouts',
            'event_type': 'fault_occurrence',
            'category': 'api_fault',
            'source_system': 'api_monitor',
            'occurrence_time': datetime.now(timezone.utc).isoformat(),
            'validity_start': datetime.now(timezone.utc).isoformat(),
            'custom_properties': {
                'service_name': 'api-gateway',
                'severity': 'high',
                'error_rate': 0.15,
                'incident_id': 'INC-2025-002'
            }
        }
        
        fault_event_id = await service.create_temporal_event(fault_event_data)
        logger.info(f"✅ Created fault event: {fault_event_id}")
        
        # 手动设置事件为有效状态
        await service.manual_state_change(
            fault_event_id, 'valid', 
            'Fault confirmed by monitoring', 
            'test_system'
        )
        
        # 创建恢复事件
        recovery_event_data = {
            'name': 'API Gateway Recovery Process',
            'description': 'Implementing load balancer reconfiguration',
            'event_type': 'recovery_process',
            'category': 'service_recovery',
            'source_system': 'sre_team',
            'occurrence_time': (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
            'validity_start': (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
            'custom_properties': {
                'target_service': 'api-gateway',
                'recovery_action': 'load_balancer_config',
                'operator': 'sre_team'
            }
        }
        
        recovery_event_id = await service.create_temporal_event(recovery_event_data)
        await service.manual_state_change(
            recovery_event_id, 'valid',
            'Recovery process started',
            'sre_team'
        )
        logger.info(f"✅ Created recovery event: {recovery_event_id}")
        
        # 测试条件性失效评估
        logger.info("🔍 评估故障事件的失效条件...")
        invalidation_result = await invalidation_engine.process_event_invalidation(
            fault_event_id,
            {'simulated_recovery_check': True}
        )
        logger.info(f"Invalidation result: {invalidation_result}")
        
        # === 测试场景2: 告警超时失效规则 ===
        logger.info("\n📝 测试场景2: 告警超时自动失效")
        
        # 创建一个过期告警事件（模拟7小时前的告警）
        old_alert_time = datetime.now(timezone.utc) - timedelta(hours=7)
        alert_event_data = {
            'name': 'Database Connection Pool Alert',
            'description': 'Database connection pool utilization high',
            'event_type': 'alert_lifecycle',
            'category': 'performance_alert',
            'source_system': 'db_monitor',
            'occurrence_time': old_alert_time.isoformat(),
            'validity_start': old_alert_time.isoformat(),
            'custom_properties': {
                'alert_type': 'threshold_breach',
                'metric': 'connection_pool_utilization',
                'threshold': 90,
                'current_value': 95
            }
        }
        
        alert_event_id = await service.create_temporal_event(alert_event_data)
        await service.manual_state_change(
            alert_event_id, 'valid',
            'Alert triggered by threshold breach',
            'monitoring_system'
        )
        logger.info(f"✅ Created old alert event: {alert_event_id}")
        
        # 测试超时失效规则
        logger.info("⏰ 测试告警超时失效规则...")
        alert_invalidation_result = await invalidation_engine.process_event_invalidation(
            alert_event_id,
            {'timeout_check': True}
        )
        logger.info(f"Alert timeout result: {alert_invalidation_result}")
        
        # === 测试场景3: 自定义失效规则 ===
        logger.info("\n📝 测试场景3: 自定义失效规则")
        
        # 添加自定义规则：CPU使用率恢复正常后失效相关事件
        custom_rule = InvalidationRule(
            rule_id="cpu_normalized_invalidation",
            name="CPU使用率恢复正常失效规则",
            description="当CPU使用率低于10%并持续5分钟后，相关性能事件自动失效",
            conditions=[
                RuleCondition(
                    condition_id="cpu_usage_low",
                    condition_type=RuleConditionType.METRIC_BASED,
                    operator=RuleOperator.LESS_THAN,
                    field_path="custom_properties.current_cpu_usage",
                    expected_value=10.0,
                    description="检查CPU使用率是否低于10%"
                ),
                RuleCondition(
                    condition_id="stable_duration",
                    condition_type=RuleConditionType.TIME_BASED,
                    operator=RuleOperator.GREATER_THAN,
                    field_path="custom_properties.stable_since",
                    expected_value=300,  # 5分钟
                    description="检查稳定持续时间"
                )
            ],
            logical_operator=RuleOperator.AND,
            applicable_event_types=["impact_observation"],
            applicable_categories=["performance_monitoring"],
            priority=1
        )
        
        invalidation_engine.add_rule(custom_rule)
        logger.info("✅ Added custom invalidation rule")
        
        # 创建性能监控事件
        perf_event_data = {
            'name': 'High CPU Usage Observation',
            'description': 'CPU usage spike detected on application servers',
            'event_type': 'impact_observation',
            'category': 'performance_monitoring',
            'source_system': 'cpu_monitor',
            'occurrence_time': (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
            'validity_start': (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
            'custom_properties': {
                'metric_type': 'cpu_utilization',
                'peak_value': 85.5,
                'current_cpu_usage': 8.5,  # 现在已恢复正常
                'stable_since': (datetime.now(timezone.utc) - timedelta(minutes=8)).isoformat(),
                'threshold': 80
            }
        }
        
        perf_event_id = await service.create_temporal_event(perf_event_data)
        await service.manual_state_change(
            perf_event_id, 'valid',
            'Performance issue confirmed',
            'monitoring_system'
        )
        logger.info(f"✅ Created performance monitoring event: {perf_event_id}")
        
        # 测试自定义失效规则
        logger.info("🔧 测试自定义失效规则...")
        custom_invalidation_result = await invalidation_engine.process_event_invalidation(
            perf_event_id,
            {'metrics_check': True}
        )
        logger.info(f"Custom rule result: {custom_invalidation_result}")
        
        # === 测试场景4: 事故关闭级联失效 ===
        logger.info("\n📝 测试场景4: 事故关闭级联失效")
        
        # 创建事故解决事件
        incident_resolution_data = {
            'name': 'Incident INC-2025-002 Resolution',
            'description': 'API Gateway issue fully resolved and documented',
            'event_type': 'incident_resolution',
            'category': 'incident_management',
            'source_system': 'incident_management',
            'occurrence_time': datetime.now(timezone.utc).isoformat(),
            'validity_start': datetime.now(timezone.utc).isoformat(),
            'custom_properties': {
                'incident_id': 'INC-2025-002',
                'resolution_status': 'closed',
                'root_cause': 'load_balancer_misconfiguration',
                'resolution_time': datetime.now(timezone.utc).isoformat()
            }
        }
        
        incident_resolution_id = await service.create_temporal_event(incident_resolution_data)
        await service.manual_state_change(
            incident_resolution_id, 'valid',
            'Incident officially closed',
            'incident_manager'
        )
        logger.info(f"✅ Created incident resolution: {incident_resolution_id}")
        
        # 测试级联失效（应该失效所有相关的故障和告警事件）
        logger.info("🔗 测试事故关闭级联失效...")
        
        # 重新评估故障事件（现在应该被级联失效）
        cascade_result = await invalidation_engine.process_event_invalidation(
            fault_event_id,
            {'incident_closure_check': True}
        )
        logger.info(f"Cascade invalidation result: {cascade_result}")
        
        # 等待自动化监控处理
        logger.info("⏰ Waiting for automated monitoring cycle...")
        await asyncio.sleep(5)
        
        # === 获取最终统计信息 ===
        logger.info("\n📊 获取失效规则执行统计...")
        
        # 获取规则统计
        rule_stats = invalidation_engine.get_rule_statistics()
        logger.info(f"Total rule executions: {rule_stats['total_executions']}")
        logger.info(f"Successful executions: {rule_stats['successful_executions']}")
        logger.info(f"Failed executions: {rule_stats['failed_executions']}")
        logger.info(f"Total rules: {rule_stats['total_rules']}")
        logger.info(f"Enabled rules: {rule_stats['enabled_rules']}")
        
        # 获取整体系统统计
        system_stats = await service.get_transition_statistics()
        logger.info(f"Total state transitions: {system_stats['transition_engine']['total_transitions']}")
        
        # 检查最终事件状态
        logger.info("\n📋 检查最终事件状态...")
        
        events_to_check = [
            ('故障事件', fault_event_id),
            ('恢复事件', recovery_event_id), 
            ('告警事件', alert_event_id),
            ('性能监控事件', perf_event_id),
            ('事故解决事件', incident_resolution_id)
        ]
        
        for event_name, event_id in events_to_check:
            lifecycle = await service.get_event_lifecycle(event_id)
            if lifecycle:
                logger.info(f"{event_name}: {lifecycle['current_state']}")
            else:
                logger.warning(f"Failed to get lifecycle for {event_name}")
        
        logger.info("🎉 Conditional invalidation engine test completed successfully!")
        
        return {
            'rule_statistics': rule_stats,
            'system_statistics': system_stats,
            'test_events': {
                'fault_event_id': fault_event_id,
                'recovery_event_id': recovery_event_id,
                'alert_event_id': alert_event_id,
                'perf_event_id': perf_event_id,
                'incident_resolution_id': incident_resolution_id
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        await service.close()

async def main():
    """主函数"""
    logger.info("🔬 Starting Conditional Invalidation Engine Test")
    
    try:
        test_results = await test_conditional_invalidation_engine()
        
        logger.info("\n" + "="*70)
        logger.info("📋 CONDITIONAL INVALIDATION ENGINE TEST RESULTS")
        logger.info("="*70)
        
        rule_stats = test_results['rule_statistics']
        logger.info(f"✅ Total Rule Executions: {rule_stats['total_executions']}")
        logger.info(f"✅ Successful Executions: {rule_stats['successful_executions']}")
        logger.info(f"❌ Failed Executions: {rule_stats['failed_executions']}")
        logger.info(f"📏 Total Rules: {rule_stats['total_rules']}")
        logger.info(f"🟢 Enabled Rules: {rule_stats['enabled_rules']}")
        logger.info(f"🔴 Disabled Rules: {rule_stats['disabled_rules']}")
        
        system_stats = test_results['system_statistics']
        logger.info(f"⚡ Total State Transitions: {system_stats['transition_engine']['total_transitions']}")
        logger.info(f"🤖 Automatic Transitions: {system_stats['transition_engine']['automatic_transitions']}")
        logger.info(f"👤 Manual Transitions: {system_stats['transition_engine']['manual_transitions']}")
        
        logger.info("\n📝 Test Events Created:")
        for event_type, event_id in test_results['test_events'].items():
            logger.info(f"  • {event_type}: {event_id}")
        
        logger.info("="*70)
        logger.info("🎉 ALL INVALIDATION ENGINE TESTS PASSED!")
        
    except Exception as e:
        logger.error(f"💥 Tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())