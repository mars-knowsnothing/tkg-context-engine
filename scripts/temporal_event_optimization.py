#!/usr/bin/env python3
"""
时序事件优化实现示例 - 基于增强设计重构故障事件

展示如何利用时序知识图谱的 valid/invalid 状态特性进行动态事件管理

关键优化点：
1. 动态状态转换：基于条件自动 valid → invalid
2. 时序约束建模：精确的时间窗口和依赖关系  
3. 生命周期管理：完整的状态变迁历史
4. 智能失效条件：基于业务逻辑的自动失效
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8001"

class TemporalEventType(str, Enum):
    FAULT_OCCURRENCE = "fault_occurrence"
    ALERT_LIFECYCLE = "alert_lifecycle"
    IMPACT_OBSERVATION = "impact_observation"
    RESPONSE_ACTION = "response_action"
    RECOVERY_PROCESS = "recovery_process"
    VALIDATION_CHECK = "validation_check"
    INCIDENT_RESOLUTION = "incident_resolution"

class ValidityState(str, Enum):
    PENDING = "pending"      # 待确认
    VALID = "valid"         # 有效
    INVALID = "invalid"     # 无效
    EXPIRED = "expired"     # 过期

@dataclass
class StateTransition:
    from_state: ValidityState
    to_state: ValidityState
    transition_time: datetime
    trigger: str
    reason: str
    automatic: bool = True

@dataclass
class TemporalEvent:
    """增强的时序事件"""
    event_id: str
    event_type: TemporalEventType
    name: str
    description: str
    
    # 时序信息
    occurrence_time: datetime
    detection_time: Optional[datetime] = None
    validity_start: datetime = None
    validity_end: Optional[datetime] = None
    
    # 状态管理
    current_state: ValidityState = ValidityState.PENDING
    state_history: List[StateTransition] = None
    
    # 失效条件
    invalidation_conditions: List[str] = None
    validation_dependencies: List[str] = None
    
    # 业务属性
    confidence: float = 1.0
    severity: str = "INFO"
    impact_scope: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.state_history is None:
            self.state_history = []
        if self.invalidation_conditions is None:
            self.invalidation_conditions = []
        if self.validation_dependencies is None:
            self.validation_dependencies = []
        if self.impact_scope is None:
            self.impact_scope = {}
        if self.validity_start is None:
            self.validity_start = self.occurrence_time

class TemporalEventOptimizer:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def create_optimized_fault_timeline(self) -> List[TemporalEvent]:
        """创建优化的故障时序事件"""
        base_time = datetime(2025, 9, 1, 8, 15, 30, tzinfo=timezone(timedelta(hours=9)))
        
        events = []
        
        # 1. 故障发生事件 - 条件性有效
        fault_event = TemporalEvent(
            event_id="FAULT-20250901-001",
            event_type=TemporalEventType.FAULT_OCCURRENCE,
            name="DATABASE_CONNECTION_TIMEOUT",
            description="数据库连接池耗尽导致连接超时",
            occurrence_time=base_time,
            detection_time=base_time + timedelta(seconds=2),
            validity_start=base_time,
            validity_end=None,  # 动态确定，基于故障解决
            current_state=ValidityState.PENDING,
            invalidation_conditions=[
                "root_cause_resolved",
                "connection_pool_restarted", 
                "service_fully_recovered",
                "incident_officially_closed"
            ],
            validation_dependencies=[
                "multiple_monitoring_sources_confirm",
                "impact_assessment_completed"
            ],
            confidence=0.95,
            severity="CRITICAL",
            impact_scope={
                "affected_services": ["ittzp-auth-service-PRO"],
                "estimated_users": 50000,
                "business_functions": ["user_authentication", "session_management"],
                "sla_breach_risk": "high"
            }
        )
        events.append(fault_event)
        
        # 2. 告警事件 - 基于阈值恢复失效
        alert_event = TemporalEvent(
            event_id="ALERT-20250901-001",
            event_type=TemporalEventType.ALERT_LIFECYCLE,
            name="ERROR_RATE_SPIKE_CRITICAL",
            description="错误率突破阈值13.75倍触发P0告警",
            occurrence_time=base_time + timedelta(seconds=15),
            validity_start=base_time + timedelta(seconds=15),
            validity_end=None,  # 当错误率恢复正常时自动失效
            current_state=ValidityState.VALID,  # 告警立即有效
            invalidation_conditions=[
                "error_rate_below_threshold_for_5min",
                "manual_alert_acknowledgment",
                "service_recovery_confirmed"
            ],
            confidence=1.0,  # 告警数据通常是确定的
            severity="P0",
            impact_scope={
                "threshold_exceeded": 13.75,
                "current_error_rate": 0.6875,
                "alert_channels": ["pagerduty", "slack", "email"]
            }
        )
        events.append(alert_event)
        
        # 3. 影响观测事件 - 短期有效性窗口
        impact_events = []
        observation_times = [
            (base_time, {"error_rate": 0.6875, "latency_ms": 5240.5, "status": "degraded"}),
            (base_time + timedelta(minutes=1), {"error_rate": 0.9, "latency_ms": 8500.0, "status": "critical"}),
            (base_time + timedelta(minutes=7, seconds=30), {"error_rate": 0.2623, "latency_ms": 1250.0, "status": "improving"}),
            (base_time + timedelta(minutes=11, seconds=30), {"error_rate": 0.0103, "latency_ms": 65.2, "status": "normal"})
        ]
        
        for i, (obs_time, metrics) in enumerate(observation_times):
            impact_event = TemporalEvent(
                event_id=f"IMPACT-OBS-{i+1:03d}",
                event_type=TemporalEventType.IMPACT_OBSERVATION,
                name=f"PERFORMANCE_METRICS_T{i+1}",
                description=f"系统性能指标观测: {metrics['status']}状态",
                occurrence_time=obs_time,
                validity_start=obs_time,
                validity_end=obs_time + timedelta(minutes=15),  # 15分钟有效期
                current_state=ValidityState.VALID,
                invalidation_conditions=[
                    "newer_observation_available",
                    "metrics_invalidated",
                    "observation_timeout"
                ],
                confidence=0.9,
                severity="INFO" if metrics['status'] == "normal" else "WARNING",
                impact_scope={
                    "metrics": metrics,
                    "observation_source": "APM_monitoring",
                    "reliability": "high"
                }
            )
            events.append(impact_event)
        
        # 4. 响应行动事件 - 执行期间有效
        response_event = TemporalEvent(
            event_id="RESPONSE-20250901-001",
            event_type=TemporalEventType.RESPONSE_ACTION,
            name="INCIDENT_RESPONSE_INITIATED",
            description="SRE-TEAM-A启动P0级事故响应流程",
            occurrence_time=base_time + timedelta(minutes=1, seconds=30),
            validity_start=base_time + timedelta(minutes=1, seconds=30),
            validity_end=base_time + timedelta(minutes=15),  # 预计15分钟响应周期
            current_state=ValidityState.VALID,
            invalidation_conditions=[
                "incident_resolved",
                "response_escalated",
                "response_timeout"
            ],
            validation_dependencies=[
                "alert_confirmed",
                "team_availability_verified"
            ],
            confidence=0.85,
            severity="HIGH",
            impact_scope={
                "response_team": "SRE-TEAM-A",
                "sla_target": "15_minutes",
                "escalation_path": "defined"
            }
        )
        events.append(response_event)
        
        # 5. 恢复过程事件 - 操作成功后失效
        recovery_event = TemporalEvent(
            event_id="RECOVERY-20250901-001",
            event_type=TemporalEventType.RECOVERY_PROCESS,
            name="CONNECTION_POOL_RESTART_OPERATION",
            description="执行数据库连接池重启恢复操作",
            occurrence_time=base_time + timedelta(minutes=4, seconds=30),
            validity_start=base_time + timedelta(minutes=4, seconds=30),
            validity_end=base_time + timedelta(minutes=9, seconds=30),  # 5分钟操作窗口
            current_state=ValidityState.VALID,
            invalidation_conditions=[
                "recovery_operation_completed",
                "recovery_operation_failed",
                "operation_timeout"
            ],
            validation_dependencies=[
                "root_cause_identified",
                "recovery_plan_approved",
                "change_management_cleared"
            ],
            confidence=0.8,  # 恢复操作有不确定性
            severity="HIGH",
            impact_scope={
                "operation_type": "service_restart",
                "estimated_downtime": "5_minutes", 
                "risk_assessment": "low",
                "rollback_plan": "available"
            }
        )
        events.append(recovery_event)
        
        # 6. 验证检查事件 - 验证完成后失效
        validation_event = TemporalEvent(
            event_id="VALIDATION-20250901-001",
            event_type=TemporalEventType.VALIDATION_CHECK,
            name="RECOVERY_SMOKE_TESTS",
            description="执行恢复后功能验证和冒烟测试",
            occurrence_time=base_time + timedelta(minutes=9, seconds=30),
            validity_start=base_time + timedelta(minutes=9, seconds=30),
            validity_end=base_time + timedelta(minutes=12),  # 2.5分钟验证窗口
            current_state=ValidityState.VALID,
            invalidation_conditions=[
                "validation_tests_completed",
                "validation_failed",
                "validation_timeout"
            ],
            validation_dependencies=[
                "recovery_operation_completed",
                "service_responding"
            ],
            confidence=0.95,
            severity="INFO",
            impact_scope={
                "test_suites": ["auth_login_flow", "token_validation", "db_connectivity"],
                "success_criteria": "95%_pass_rate",
                "validation_scope": "critical_functions"
            }
        )
        events.append(validation_event)
        
        # 7. 事故解决事件 - 永久有效记录
        resolution_event = TemporalEvent(
            event_id="RESOLUTION-20250901-001",
            event_type=TemporalEventType.INCIDENT_RESOLUTION,
            name="INCIDENT_OFFICIALLY_RESOLVED",
            description="事故正式宣告解决，服务完全恢复正常",
            occurrence_time=base_time + timedelta(minutes=14, seconds=30),
            validity_start=base_time + timedelta(minutes=14, seconds=30),
            validity_end=None,  # 解决记录永久有效
            current_state=ValidityState.VALID,
            invalidation_conditions=[
                "resolution_disputed",
                "incident_reoccurred_within_24h"
            ],
            validation_dependencies=[
                "all_systems_restored",
                "validation_tests_passed",
                "stakeholder_confirmation"
            ],
            confidence=0.99,
            severity="INFO",
            impact_scope={
                "total_incident_duration": "14m30s",
                "affected_user_minutes": 725000,  # 50k users * 14.5 min
                "sla_status": "met",
                "business_impact": "minimal"
            }
        )
        events.append(resolution_event)
        
        return events

    def simulate_state_transitions(self, events: List[TemporalEvent]) -> Dict[str, List[StateTransition]]:
        """模拟事件状态转换"""
        transitions = {}
        
        for event in events:
            event_transitions = []
            
            # 初始状态转换
            if event.current_state == ValidityState.PENDING:
                # PENDING → VALID 转换
                valid_time = event.validity_start
                if event.validation_dependencies:
                    # 模拟依赖满足后的延迟
                    valid_time = event.occurrence_time + timedelta(seconds=30)
                
                event_transitions.append(StateTransition(
                    from_state=ValidityState.PENDING,
                    to_state=ValidityState.VALID,
                    transition_time=valid_time,
                    trigger="validation_dependencies_satisfied",
                    reason=f"依赖条件满足: {', '.join(event.validation_dependencies)}",
                    automatic=True
                ))
            
            # 失效转换（基于失效条件）
            if event.invalidation_conditions:
                invalid_time = self._calculate_invalidation_time(event)
                if invalid_time:
                    event_transitions.append(StateTransition(
                        from_state=ValidityState.VALID,
                        to_state=ValidityState.INVALID,
                        transition_time=invalid_time,
                        trigger="invalidation_condition_met",
                        reason=f"失效条件触发: {event.invalidation_conditions[0]}",
                        automatic=True
                    ))
            
            # 过期转换
            if event.validity_end:
                event_transitions.append(StateTransition(
                    from_state=ValidityState.VALID,
                    to_state=ValidityState.EXPIRED,
                    transition_time=event.validity_end,
                    trigger="validity_period_ended",
                    reason="有效期自然结束",
                    automatic=True
                ))
            
            transitions[event.event_id] = event_transitions
        
        return transitions

    def _calculate_invalidation_time(self, event: TemporalEvent) -> Optional[datetime]:
        """计算事件失效时间"""
        base_time = datetime(2025, 9, 1, 8, 15, 30, tzinfo=timezone(timedelta(hours=9)))
        
        # 基于事件类型和失效条件计算失效时间
        if event.event_type == TemporalEventType.FAULT_OCCURRENCE:
            # 故障在解决时失效
            return base_time + timedelta(minutes=14, seconds=30)
        elif event.event_type == TemporalEventType.ALERT_LIFECYCLE:
            # 告警在服务恢复时失效
            return base_time + timedelta(minutes=14, seconds=45)
        elif event.event_type == TemporalEventType.RECOVERY_PROCESS:
            # 恢复操作在完成时失效
            return base_time + timedelta(minutes=7, seconds=30)
        elif event.event_type == TemporalEventType.VALIDATION_CHECK:
            # 验证在完成时失效
            return base_time + timedelta(minutes=11, seconds=30)
        
        return None

    def generate_temporal_queries(self) -> List[Dict[str, Any]]:
        """生成时序查询示例"""
        base_time = datetime(2025, 9, 1, 8, 15, 30, tzinfo=timezone(timedelta(hours=9)))
        
        queries = [
            {
                "description": "故障发生时刻的有效事件",
                "query_time": base_time,
                "expected_states": ["FAULT-事件PENDING", "其他事件未发生"]
            },
            {
                "description": "告警触发后的事件状态",
                "query_time": base_time + timedelta(minutes=2),
                "expected_states": ["FAULT-VALID", "ALERT-VALID", "IMPACT-VALID"]
            },
            {
                "description": "恢复操作期间的有效事件", 
                "query_time": base_time + timedelta(minutes=6),
                "expected_states": ["FAULT-VALID", "ALERT-VALID", "RECOVERY-VALID", "RESPONSE-VALID"]
            },
            {
                "description": "事故解决后的事件状态",
                "query_time": base_time + timedelta(minutes=16),
                "expected_states": ["RESOLUTION-VALID", "其他关键事件-INVALID"]
            },
            {
                "description": "24小时后的历史事件状态",
                "query_time": base_time + timedelta(days=1),
                "expected_states": ["大部分事件-EXPIRED", "RESOLUTION-VALID"]
            }
        ]
        
        return queries

    async def create_knowledge_node_with_temporal(self, event: TemporalEvent) -> dict:
        """创建带时序信息的知识节点"""
        node_data = {
            "name": event.name,
            "type": "event",
            "content": f"{event.description} [时序事件类型: {event.event_type.value}]",
            "properties": {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "occurrence_time": event.occurrence_time.isoformat(),
                "detection_time": event.detection_time.isoformat() if event.detection_time else None,
                "current_state": event.current_state.value,
                "confidence": event.confidence,
                "severity": event.severity,
                "impact_scope": event.impact_scope,
                "invalidation_conditions": event.invalidation_conditions,
                "validation_dependencies": event.validation_dependencies,
                "temporal_optimization": "enabled"
            },
            "valid_time": {
                "start_time": event.validity_start.isoformat(),
                "end_time": event.validity_end.isoformat() if event.validity_end else None
            },
            "effective_time": event.occurrence_time.isoformat()
        }
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/knowledge/",
                json=node_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✅ 创建时序优化节点: {event.name} [{event.current_state.value}]")
            return result
        except httpx.HTTPError as e:
            logger.error(f"❌ 创建节点失败: {e}")
            return None

    async def demonstrate_temporal_optimization(self):
        """演示时序优化效果"""
        logger.info("🚀 开始时序事件优化演示")
        logger.info("=" * 80)
        
        # 1. 创建优化的事件
        events = self.create_optimized_fault_timeline()
        logger.info(f"📅 创建了 {len(events)} 个优化的时序事件")
        
        # 2. 模拟状态转换
        transitions = self.simulate_state_transitions(events)
        logger.info("🔄 模拟事件状态转换：")
        for event_id, trans_list in transitions.items():
            for trans in trans_list:
                logger.info(f"   {event_id}: {trans.from_state.value} → {trans.to_state.value} "
                          f"@ {trans.transition_time.strftime('%H:%M:%S')} ({trans.reason})")
        
        # 3. 导入优化的事件到系统
        logger.info("\n📦 导入优化事件到知识图谱：")
        created_nodes = []
        for event in events:
            node = await self.create_knowledge_node_with_temporal(event)
            if node:
                created_nodes.append(node)
            await asyncio.sleep(0.1)
        
        # 4. 生成时序查询示例
        queries = self.generate_temporal_queries()
        logger.info(f"\n🔍 生成 {len(queries)} 个时序查询示例：")
        for i, query in enumerate(queries, 1):
            logger.info(f"   {i}. {query['description']}")
            logger.info(f"      查询时间: {query['query_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"      预期状态: {', '.join(query['expected_states'])}")
        
        # 5. 输出优化效果总结
        self.print_optimization_summary(events, transitions, created_nodes)

    def print_optimization_summary(self, events: List[TemporalEvent], 
                                 transitions: Dict[str, List[StateTransition]], 
                                 created_nodes: List[dict]):
        """打印优化效果总结"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 时序事件优化效果总结")
        logger.info("=" * 80)
        
        # 事件类型统计
        event_types = {}
        for event in events:
            event_types[event.event_type.value] = event_types.get(event.event_type.value, 0) + 1
        
        logger.info("🏷️  事件类型分布:")
        for event_type, count in event_types.items():
            logger.info(f"   {event_type}: {count} 个")
        
        # 状态转换统计
        total_transitions = sum(len(trans_list) for trans_list in transitions.values())
        logger.info(f"🔄 总状态转换数: {total_transitions}")
        
        # 时序特性统计
        conditional_events = len([e for e in events if e.invalidation_conditions])
        dependent_events = len([e for e in events if e.validation_dependencies])
        
        logger.info("⚡ 时序特性统计:")
        logger.info(f"   条件性失效事件: {conditional_events}/{len(events)}")
        logger.info(f"   依赖验证事件: {dependent_events}/{len(events)}")
        logger.info(f"   成功导入节点: {len(created_nodes)}/{len(events)}")
        
        logger.info("\n🎯 优化改进点:")
        logger.info("   ✅ 动态状态转换: 事件状态基于业务条件自动变化")
        logger.info("   ✅ 精确时序约束: 每个事件有明确的有效时间窗口")
        logger.info("   ✅ 智能失效机制: 基于业务逻辑的自动失效条件")
        logger.info("   ✅ 生命周期管理: 完整记录事件从产生到消亡")
        logger.info("   ✅ 上下文感知: 丰富的影响范围和依赖关系信息")
        
        logger.info("\n💡 应用价值:")
        logger.info("   🔍 精确时点查询: 查询任意时刻的有效事件集合")
        logger.info("   📈 动态分析: 追踪事件有效性随时间的变化")
        logger.info("   🧠 智能推理: 基于状态转换进行因果推理")
        logger.info("   📋 完整审计: 提供事件生命周期的完整历史")
        
        logger.info("=" * 80)

async def main():
    """主演示程序"""
    logger.info("🔥 TKG Context Engine - 时序事件优化演示")
    
    async with TemporalEventOptimizer(API_BASE_URL) as optimizer:
        try:
            # 检查API连通性
            response = await optimizer.client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                logger.error("❌ 后端API不可用")
                return
            logger.info("✅ 后端API连接正常")
            
            # 执行优化演示
            await optimizer.demonstrate_temporal_optimization()
            
        except Exception as e:
            logger.error(f"❌ 演示过程中发生错误: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())