# 动态状态转换引擎实现

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field

from ..models.temporal_schemas import (
    TemporalEventNode, 
    TemporalValidityState, 
    StateTransition,
    InvalidationCondition,
    ValidationDependency
)
from .temporal_db_service import TemporalDatabaseService
from .conditional_invalidation_engine import ConditionalInvalidationEngine

logger = logging.getLogger(__name__)

class TransitionTriggerType(str, Enum):
    """状态转换触发类型"""
    TIME_BASED = "time_based"           # 时间驱动
    CONDITION_BASED = "condition_based" # 条件驱动
    EVENT_DRIVEN = "event_driven"       # 事件驱动
    MANUAL = "manual"                   # 手动触发
    DEPENDENCY = "dependency"           # 依赖触发

class TransitionResult(Enum):
    """状态转换结果"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    PENDING = "pending"

@dataclass
class TransitionRule:
    """状态转换规则定义"""
    rule_id: str
    from_states: List[TemporalValidityState]
    to_state: TemporalValidityState
    trigger_type: TransitionTriggerType
    condition_expression: str
    priority: int = 1
    auto_execute: bool = True
    timeout_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TransitionContext:
    """状态转换上下文"""
    event_id: str
    trigger_source: str
    trigger_time: datetime
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    execution_context: Dict[str, Any] = field(default_factory=dict)

class StateTransitionEngine:
    """动态状态转换引擎"""
    
    def __init__(self, temporal_db: TemporalDatabaseService):
        self.temporal_db = temporal_db
        self.invalidation_engine = ConditionalInvalidationEngine(temporal_db)
        self.transition_rules: Dict[str, TransitionRule] = {}
        self.condition_evaluators: Dict[str, Callable] = {}
        self.active_monitors: Dict[str, asyncio.Task] = {}
        self.transition_history: List[Dict[str, Any]] = []
        
        # 注册默认条件评估器
        self._register_default_evaluators()
        
        # 加载默认转换规则
        self._load_default_transition_rules()
    
    def _register_default_evaluators(self):
        """注册默认的条件评估器"""
        
        async def time_elapsed_evaluator(event: TemporalEventNode, condition: str, context: TransitionContext) -> bool:
            """时间流逝条件评估器"""
            try:
                # 解析条件: "time_elapsed:300" (300秒后)
                seconds = int(condition.split(':')[1])
                elapsed = (context.trigger_time - event.validity_context.occurrence_time).total_seconds()
                return elapsed >= seconds
            except:
                return False
        
        async def service_restored_evaluator(event: TemporalEventNode, condition: str, context: TransitionContext) -> bool:
            """服务恢复条件评估器"""
            # 检查相关的恢复事件是否存在且有效
            try:
                service_name = event.custom_properties.get('service_name', '')
                if not service_name:
                    return False
                
                # 查询恢复事件
                recovery_events = await self.temporal_db.get_events_at_time(
                    context.trigger_time,
                    event_types=['RECOVERY_PROCESS'],
                    categories=['service_recovery']
                )
                
                # 检查是否有针对此服务的有效恢复事件
                for recovery_event in recovery_events:
                    if (recovery_event.get('source_system') == service_name and 
                        recovery_event.get('current_state') == 'valid'):
                        return True
                
                return False
            except Exception as e:
                logger.error(f"Service restored evaluation failed: {e}")
                return False
        
        async def threshold_exceeded_evaluator(event: TemporalEventNode, condition: str, context: TransitionContext) -> bool:
            """阈值超出条件评估器"""
            try:
                # 解析条件: "threshold_exceeded:error_rate:0.05"
                parts = condition.split(':')
                metric_name = parts[1]
                threshold = float(parts[2])
                
                # 从触发数据中获取指标值
                metric_value = context.trigger_data.get(metric_name, 0)
                return float(metric_value) > threshold
            except:
                return False
        
        async def incident_closed_evaluator(event: TemporalEventNode, condition: str, context: TransitionContext) -> bool:
            """事故关闭条件评估器"""
            try:
                incident_id = event.custom_properties.get('incident_id')
                if not incident_id:
                    return False
                
                # 查询事故解决事件
                resolution_events = await self.temporal_db.get_events_at_time(
                    context.trigger_time,
                    event_types=['INCIDENT_RESOLUTION'],
                    states=['valid']
                )
                
                # 检查是否有对应的解决事件
                for resolution in resolution_events:
                    if resolution.get('custom_properties', {}).get('incident_id') == incident_id:
                        return True
                
                return False
            except Exception as e:
                logger.error(f"Incident closed evaluation failed: {e}")
                return False
        
        async def manual_confirmation_evaluator(event: TemporalEventNode, condition: str, context: TransitionContext) -> bool:
            """手动确认条件评估器"""
            # 检查触发数据中是否包含手动确认标记
            return context.trigger_data.get('manual_confirmation', False) is True
        
        # 注册评估器
        self.condition_evaluators = {
            'time_elapsed': time_elapsed_evaluator,
            'service_restored': service_restored_evaluator,
            'threshold_exceeded': threshold_exceeded_evaluator,
            'incident_closed': incident_closed_evaluator,
            'manual_confirmation': manual_confirmation_evaluator
        }
    
    def _load_default_transition_rules(self):
        """加载默认的状态转换规则"""
        
        default_rules = [
            # 故障事件转换规则
            TransitionRule(
                rule_id="fault_pending_to_valid",
                from_states=[TemporalValidityState.PENDING],
                to_state=TemporalValidityState.VALID,
                trigger_type=TransitionTriggerType.CONDITION_BASED,
                condition_expression="threshold_exceeded:error_rate:0.05",
                priority=1,
                metadata={"description": "错误率超阈值时确认故障"}
            ),
            
            TransitionRule(
                rule_id="fault_valid_to_invalid",
                from_states=[TemporalValidityState.VALID],
                to_state=TemporalValidityState.INVALID,
                trigger_type=TransitionTriggerType.CONDITION_BASED,
                condition_expression="service_restored",
                priority=1,
                metadata={"description": "服务恢复后故障失效"}
            ),
            
            # 告警生命周期规则
            TransitionRule(
                rule_id="alert_pending_to_valid",
                from_states=[TemporalValidityState.PENDING],
                to_state=TemporalValidityState.VALID,
                trigger_type=TransitionTriggerType.TIME_BASED,
                condition_expression="time_elapsed:30",
                priority=2,
                metadata={"description": "告警30秒后自动生效"}
            ),
            
            TransitionRule(
                rule_id="alert_valid_to_invalid",
                from_states=[TemporalValidityState.VALID],
                to_state=TemporalValidityState.INVALID,
                trigger_type=TransitionTriggerType.CONDITION_BASED,
                condition_expression="incident_closed",
                priority=1,
                metadata={"description": "事故关闭后告警失效"}
            ),
            
            # 恢复过程规则
            TransitionRule(
                rule_id="recovery_auto_expire",
                from_states=[TemporalValidityState.VALID],
                to_state=TemporalValidityState.EXPIRED,
                trigger_type=TransitionTriggerType.TIME_BASED,
                condition_expression="time_elapsed:3600",
                priority=3,
                metadata={"description": "恢复过程1小时后自动过期"}
            ),
            
            # 手动确认规则
            TransitionRule(
                rule_id="manual_confirmation",
                from_states=[TemporalValidityState.PENDING, TemporalValidityState.DISPUTED],
                to_state=TemporalValidityState.VALID,
                trigger_type=TransitionTriggerType.MANUAL,
                condition_expression="manual_confirmation",
                priority=1,
                auto_execute=False,
                metadata={"description": "手动确认事件有效性"}
            )
        ]
        
        for rule in default_rules:
            self.transition_rules[rule.rule_id] = rule
        
        logger.info(f"Loaded {len(default_rules)} default transition rules")
    
    def add_transition_rule(self, rule: TransitionRule):
        """添加自定义转换规则"""
        self.transition_rules[rule.rule_id] = rule
        logger.info(f"Added transition rule: {rule.rule_id}")
    
    def add_condition_evaluator(self, condition_type: str, evaluator: Callable):
        """添加自定义条件评估器"""
        self.condition_evaluators[condition_type] = evaluator
        logger.info(f"Added condition evaluator: {condition_type}")
    
    async def evaluate_transition_conditions(self, 
                                           event: TemporalEventNode, 
                                           context: TransitionContext) -> List[TransitionRule]:
        """评估事件的状态转换条件"""
        applicable_rules = []
        
        for rule in self.transition_rules.values():
            # 检查当前状态是否匹配
            if event.current_state not in rule.from_states:
                continue
            
            try:
                # 解析条件表达式
                condition_parts = rule.condition_expression.split(':')
                condition_type = condition_parts[0]
                
                # 获取对应的评估器
                evaluator = self.condition_evaluators.get(condition_type)
                if not evaluator:
                    logger.warning(f"No evaluator found for condition type: {condition_type}")
                    continue
                
                # 评估条件
                condition_met = await evaluator(event, rule.condition_expression, context)
                
                if condition_met:
                    applicable_rules.append(rule)
                    logger.debug(f"Condition met for rule {rule.rule_id}: {rule.condition_expression}")
                
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
                continue
        
        # 按优先级排序
        applicable_rules.sort(key=lambda r: r.priority)
        return applicable_rules
    
    async def execute_state_transition(self, 
                                     event_id: str, 
                                     rule: TransitionRule,
                                     context: TransitionContext) -> TransitionResult:
        """执行状态转换"""
        try:
            # 获取当前事件
            event_data = await self.temporal_db.get_temporal_event(event_id)
            if not event_data:
                logger.error(f"Event not found: {event_id}")
                return TransitionResult.FAILED
            
            # 执行状态转换
            success = await self.temporal_db.update_event_state(
                event_id=event_id,
                new_state=rule.to_state.value,
                trigger=context.trigger_source,
                reason=f"Automatic transition via rule: {rule.rule_id}",
                automatic=rule.auto_execute
            )
            
            if success:
                # 记录转换历史
                self.transition_history.append({
                    'event_id': event_id,
                    'rule_id': rule.rule_id,
                    'from_state': event_data['event']['current_state'],
                    'to_state': rule.to_state.value,
                    'transition_time': context.trigger_time.isoformat(),
                    'trigger_source': context.trigger_source,
                    'automatic': rule.auto_execute
                })
                
                logger.info(f"State transition successful: {event_id} -> {rule.to_state.value}")
                return TransitionResult.SUCCESS
            else:
                logger.error(f"State transition failed: {event_id}")
                return TransitionResult.FAILED
                
        except Exception as e:
            logger.error(f"Error executing state transition: {e}")
            return TransitionResult.FAILED
    
    async def process_event_transitions(self, 
                                      event_id: str, 
                                      trigger_source: str,
                                      trigger_data: Optional[Dict[str, Any]] = None) -> List[TransitionResult]:
        """处理事件的状态转换"""
        results = []
        
        try:
            # 获取事件
            event_data = await self.temporal_db.get_temporal_event(event_id)
            if not event_data:
                logger.warning(f"Event not found: {event_id}")
                return [TransitionResult.FAILED]
            
            # 构建转换上下文
            context = TransitionContext(
                event_id=event_id,
                trigger_source=trigger_source,
                trigger_time=datetime.now(timezone.utc),
                trigger_data=trigger_data or {},
            )
            
            # 反序列化事件对象 (简化版本，实际需要完整反序列化)
            event = type('Event', (), {
                'event_id': event_data['event']['event_id'],
                'current_state': TemporalValidityState(event_data['event']['current_state']),
                'validity_context': type('Context', (), {
                    'occurrence_time': datetime.fromisoformat(event_data['event']['occurrence_time'].replace('Z', '+00:00')),
                })(),
                'custom_properties': event_data['event'].get('custom_properties', {})
            })()
            
            # 评估适用的转换规则
            applicable_rules = await self.evaluate_transition_conditions(event, context)
            
            if not applicable_rules:
                logger.debug(f"No applicable transition rules for event: {event_id}")
                return [TransitionResult.PENDING]
            
            # 执行转换规则（通常只执行优先级最高的）
            for rule in applicable_rules[:1]:  # 只执行第一个规则
                if rule.auto_execute:
                    result = await self.execute_state_transition(event_id, rule, context)
                    results.append(result)
                    
                    # 如果转换成功，检查是否有级联转换
                    if result == TransitionResult.SUCCESS:
                        await self._process_cascade_transitions(event_id, rule, context)
                else:
                    results.append(TransitionResult.PENDING)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing event transitions: {e}")
            return [TransitionResult.FAILED]
    
    async def _process_cascade_transitions(self, 
                                         event_id: str, 
                                         triggering_rule: TransitionRule,
                                         context: TransitionContext):
        """处理级联状态转换"""
        try:
            # 查找依赖此事件的其他事件
            # 这里需要查询图数据库中的依赖关系
            dependent_events_query = """
            MATCH (source:TemporalEvent {event_id: $event_id})<-[:DEPENDS_ON]-(dependent:TemporalEvent)
            RETURN dependent.event_id as dependent_id
            """
            
            dependent_results = await self.temporal_db.falkordb.execute_query(
                dependent_events_query, 
                {'event_id': event_id}
            )
            
            # 对每个依赖事件触发状态转换检查
            for result in dependent_results:
                dependent_id = result['dependent_id']
                await self.process_event_transitions(
                    dependent_id, 
                    f"cascade_from_{event_id}",
                    {'cascade_trigger': True, 'source_event': event_id}
                )
                
        except Exception as e:
            logger.error(f"Error processing cascade transitions: {e}")
    
    async def start_automated_monitoring(self, check_interval: int = 60):
        """启动自动化状态监控"""
        if "automated_monitor" in self.active_monitors:
            logger.warning("Automated monitoring already running")
            return
        
        async def monitoring_loop():
            while True:
                try:
                    await self._perform_automated_checks()
                    await asyncio.sleep(check_interval)
                except asyncio.CancelledError:
                    logger.info("Automated monitoring cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in automated monitoring: {e}")
                    await asyncio.sleep(check_interval)
        
        self.active_monitors["automated_monitor"] = asyncio.create_task(monitoring_loop())
        logger.info(f"Started automated state monitoring with {check_interval}s interval")
    
    async def _perform_automated_checks(self):
        """执行自动化状态检查"""
        try:
            # 获取所有需要检查的事件
            current_time = datetime.now(timezone.utc)
            
            # 查询所有非最终状态的事件
            active_events_query = """
            MATCH (event:TemporalEvent)
            WHERE event.current_state IN ['pending', 'valid', 'suspended']
            RETURN event.event_id as event_id
            """
            
            active_events = await self.temporal_db.falkordb.execute_query(active_events_query)
            
            # 对每个活跃事件检查转换条件和失效规则
            for event_result in active_events:
                event_id = event_result['event_id']
                
                # 检查状态转换
                await self.process_event_transitions(
                    event_id, 
                    "automated_monitoring",
                    {'check_time': current_time.isoformat()}
                )
                
                # 检查条件性失效规则
                await self.invalidation_engine.process_event_invalidation(
                    event_id,
                    {'check_time': current_time.isoformat(), 'automated': True}
                )
            
            logger.debug(f"Automated check completed for {len(active_events)} events")
            
        except Exception as e:
            logger.error(f"Error in automated checks: {e}")
    
    async def stop_monitoring(self):
        """停止所有监控任务"""
        for task_name, task in self.active_monitors.items():
            task.cancel()
            logger.info(f"Stopped monitoring task: {task_name}")
        
        self.active_monitors.clear()
    
    def get_transition_statistics(self) -> Dict[str, Any]:
        """获取状态转换统计信息"""
        if not self.transition_history:
            return {"total_transitions": 0}
        
        stats = {
            "total_transitions": len(self.transition_history),
            "automatic_transitions": sum(1 for t in self.transition_history if t['automatic']),
            "manual_transitions": sum(1 for t in self.transition_history if not t['automatic']),
            "transitions_by_rule": {},
            "transitions_by_state": {},
            "recent_transitions": self.transition_history[-10:]  # 最近10次转换
        }
        
        # 按规则统计
        for transition in self.transition_history:
            rule_id = transition['rule_id']
            stats["transitions_by_rule"][rule_id] = stats["transitions_by_rule"].get(rule_id, 0) + 1
        
        # 按状态统计
        for transition in self.transition_history:
            to_state = transition['to_state']
            stats["transitions_by_state"][to_state] = stats["transitions_by_state"].get(to_state, 0) + 1
        
        return stats
    
    async def manual_trigger_transition(self, 
                                      event_id: str, 
                                      target_state: TemporalValidityState,
                                      reason: str,
                                      operator: str) -> TransitionResult:
        """手动触发状态转换"""
        try:
            # 构建手动触发上下文
            context = TransitionContext(
                event_id=event_id,
                trigger_source=f"manual_operator_{operator}",
                trigger_time=datetime.now(timezone.utc),
                trigger_data={
                    'manual_confirmation': True,
                    'operator': operator,
                    'reason': reason
                }
            )
            
            # 查找适用的手动转换规则
            manual_rules = [
                rule for rule in self.transition_rules.values()
                if (rule.trigger_type == TransitionTriggerType.MANUAL and
                    target_state in [rule.to_state] and
                    not rule.auto_execute)
            ]
            
            if manual_rules:
                # 执行第一个匹配的手动规则
                rule = manual_rules[0]
                result = await self.execute_state_transition(event_id, rule, context)
                
                logger.info(f"Manual transition executed by {operator}: {event_id} -> {target_state.value}")
                return result
            else:
                # 直接执行状态更新（绕过规则系统）
                success = await self.temporal_db.update_event_state(
                    event_id=event_id,
                    new_state=target_state.value,
                    trigger=f"manual_operator_{operator}",
                    reason=reason,
                    automatic=False
                )
                
                return TransitionResult.SUCCESS if success else TransitionResult.FAILED
            
        except Exception as e:
            logger.error(f"Error in manual transition trigger: {e}")
            return TransitionResult.FAILED