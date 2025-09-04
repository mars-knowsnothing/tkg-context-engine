# 条件性失效规则引擎实现

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from ..models.temporal_schemas import (
    TemporalEventNode, 
    TemporalValidityState, 
    InvalidationCondition
)
from .temporal_db_service import TemporalDatabaseService

logger = logging.getLogger(__name__)

class RuleOperator(str, Enum):
    """规则操作符"""
    AND = "and"
    OR = "or"
    NOT = "not"
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "ge"
    LESS_EQUAL = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    MATCHES = "matches"
    EXISTS = "exists"

class RuleConditionType(str, Enum):
    """规则条件类型"""
    TIME_BASED = "time_based"          # 时间条件
    METRIC_BASED = "metric_based"      # 指标条件
    EVENT_BASED = "event_based"        # 事件条件
    STATE_BASED = "state_based"        # 状态条件
    DEPENDENCY = "dependency"          # 依赖条件
    CUSTOM = "custom"                  # 自定义条件

@dataclass
class RuleCondition:
    """规则条件定义"""
    condition_id: str
    condition_type: RuleConditionType
    operator: RuleOperator
    field_path: str  # 字段路径，如 "custom_properties.error_rate"
    expected_value: Any
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class InvalidationRule:
    """失效规则定义"""
    rule_id: str
    name: str
    description: str
    conditions: List[RuleCondition]
    logical_operator: RuleOperator = RuleOperator.AND  # 条件间的逻辑关系
    target_states: List[TemporalValidityState] = field(default_factory=lambda: [TemporalValidityState.INVALID])
    priority: int = 1
    enabled: bool = True
    auto_execute: bool = True
    cooldown_seconds: Optional[int] = None
    applicable_event_types: Optional[List[str]] = None
    applicable_categories: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class RuleEvaluationContext:
    """规则评估上下文"""
    def __init__(self, 
                 event_id: str, 
                 event_data: Dict[str, Any],
                 current_time: datetime,
                 external_data: Optional[Dict[str, Any]] = None):
        self.event_id = event_id
        self.event_data = event_data
        self.current_time = current_time
        self.external_data = external_data or {}
        self.evaluation_cache: Dict[str, Any] = {}

class BaseConditionEvaluator(ABC):
    """条件评估器基类"""
    
    @abstractmethod
    async def evaluate(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        """评估条件是否满足"""
        pass

class TimeBasedEvaluator(BaseConditionEvaluator):
    """时间条件评估器"""
    
    async def evaluate(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        try:
            field_value = self._get_field_value(condition.field_path, context.event_data)
            if not field_value:
                return False
            
            event_time = datetime.fromisoformat(field_value.replace('Z', '+00:00'))
            expected_value = condition.expected_value
            
            if condition.operator == RuleOperator.GREATER_THAN:
                # 时间差大于预期值（秒）
                time_diff = (context.current_time - event_time).total_seconds()
                return time_diff > expected_value
            elif condition.operator == RuleOperator.LESS_THAN:
                time_diff = (context.current_time - event_time).total_seconds()
                return time_diff < expected_value
            elif condition.operator == RuleOperator.GREATER_EQUAL:
                time_diff = (context.current_time - event_time).total_seconds()
                return time_diff >= expected_value
            elif condition.operator == RuleOperator.LESS_EQUAL:
                time_diff = (context.current_time - event_time).total_seconds()
                return time_diff <= expected_value
            
            return False
            
        except Exception as e:
            logger.error(f"Time-based evaluation error: {e}")
            return False
    
    def _get_field_value(self, field_path: str, data: Dict[str, Any]):
        """获取嵌套字段值"""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value

class MetricBasedEvaluator(BaseConditionEvaluator):
    """指标条件评估器"""
    
    async def evaluate(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        try:
            field_value = self._get_field_value(condition.field_path, context.event_data)
            if field_value is None:
                return False
            
            expected_value = condition.expected_value
            
            # 数值比较
            if condition.operator == RuleOperator.GREATER_THAN:
                return float(field_value) > float(expected_value)
            elif condition.operator == RuleOperator.LESS_THAN:
                return float(field_value) < float(expected_value)
            elif condition.operator == RuleOperator.GREATER_EQUAL:
                return float(field_value) >= float(expected_value)
            elif condition.operator == RuleOperator.LESS_EQUAL:
                return float(field_value) <= float(expected_value)
            elif condition.operator == RuleOperator.EQUALS:
                return float(field_value) == float(expected_value)
            elif condition.operator == RuleOperator.NOT_EQUALS:
                return float(field_value) != float(expected_value)
            
            return False
            
        except Exception as e:
            logger.error(f"Metric-based evaluation error: {e}")
            return False
    
    def _get_field_value(self, field_path: str, data: Dict[str, Any]):
        """获取嵌套字段值"""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value

class EventBasedEvaluator(BaseConditionEvaluator):
    """事件条件评估器"""
    
    def __init__(self, temporal_db: TemporalDatabaseService):
        self.temporal_db = temporal_db
    
    async def evaluate(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        try:
            # 查询相关事件
            if condition.operator == RuleOperator.EXISTS:
                # 检查是否存在满足条件的事件
                return await self._check_event_exists(condition, context)
            elif condition.operator == RuleOperator.NOT:
                # 检查不存在满足条件的事件
                exists = await self._check_event_exists(condition, context)
                return not exists
            
            return False
            
        except Exception as e:
            logger.error(f"Event-based evaluation error: {e}")
            return False
    
    async def _check_event_exists(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        """检查事件是否存在"""
        try:
            expected_criteria = condition.expected_value
            if not isinstance(expected_criteria, dict):
                return False
            
            # 构建查询参数
            event_types = expected_criteria.get('event_types', [])
            categories = expected_criteria.get('categories', [])
            states = expected_criteria.get('states', [])
            
            # 查询当前时间点的有效事件
            events = await self.temporal_db.get_events_at_time(
                timestamp=context.current_time.isoformat(),
                event_types=event_types if event_types else None,
                states=states if states else None,
                categories=categories if categories else None
            )
            
            # 进一步过滤事件
            matching_events = []
            for event in events:
                if self._event_matches_criteria(event, expected_criteria):
                    matching_events.append(event)
            
            return len(matching_events) > 0
            
        except Exception as e:
            logger.error(f"Event existence check error: {e}")
            return False
    
    def _event_matches_criteria(self, event: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """检查事件是否匹配条件"""
        for field, expected in criteria.items():
            if field in ['event_types', 'categories', 'states']:
                continue  # 这些已在查询中处理
            
            event_value = event.get(field)
            if event_value != expected:
                return False
        
        return True

class StateBasedEvaluator(BaseConditionEvaluator):
    """状态条件评估器"""
    
    def __init__(self, temporal_db: TemporalDatabaseService):
        self.temporal_db = temporal_db
    
    async def evaluate(self, condition: RuleCondition, context: RuleEvaluationContext) -> bool:
        try:
            current_state = context.event_data.get('current_state')
            expected_states = condition.expected_value
            
            if not isinstance(expected_states, list):
                expected_states = [expected_states]
            
            if condition.operator == RuleOperator.IN:
                return current_state in expected_states
            elif condition.operator == RuleOperator.NOT_IN:
                return current_state not in expected_states
            elif condition.operator == RuleOperator.EQUALS:
                return current_state == condition.expected_value
            elif condition.operator == RuleOperator.NOT_EQUALS:
                return current_state != condition.expected_value
            
            return False
            
        except Exception as e:
            logger.error(f"State-based evaluation error: {e}")
            return False

class ConditionalInvalidationEngine:
    """条件性失效规则引擎"""
    
    def __init__(self, temporal_db: TemporalDatabaseService):
        self.temporal_db = temporal_db
        self.rules: Dict[str, InvalidationRule] = {}
        self.evaluators: Dict[RuleConditionType, BaseConditionEvaluator] = {}
        self.rule_execution_history: List[Dict[str, Any]] = []
        self.cooldown_tracker: Dict[str, datetime] = {}
        
        # 注册默认评估器
        self._register_default_evaluators()
        
        # 加载默认规则
        self._load_default_rules()
    
    def _register_default_evaluators(self):
        """注册默认条件评估器"""
        self.evaluators = {
            RuleConditionType.TIME_BASED: TimeBasedEvaluator(),
            RuleConditionType.METRIC_BASED: MetricBasedEvaluator(),
            RuleConditionType.EVENT_BASED: EventBasedEvaluator(self.temporal_db),
            RuleConditionType.STATE_BASED: StateBasedEvaluator(self.temporal_db)
        }
    
    def _load_default_rules(self):
        """加载默认的失效规则"""
        
        default_rules = [
            # 故障自动失效规则：服务恢复后故障失效
            InvalidationRule(
                rule_id="fault_auto_invalidate_on_recovery",
                name="故障自动失效规则",
                description="当检测到服务恢复事件时，自动失效相关故障事件",
                conditions=[
                    RuleCondition(
                        condition_id="recovery_event_exists",
                        condition_type=RuleConditionType.EVENT_BASED,
                        operator=RuleOperator.EXISTS,
                        field_path="custom_properties.service_name",
                        expected_value={
                            "event_types": ["recovery_process"],
                            "states": ["valid"],
                            "custom_properties.target_service": None  # 将动态设置
                        },
                        description="检查是否存在对应的恢复事件"
                    )
                ],
                applicable_event_types=["fault_occurrence"],
                priority=1
            ),
            
            # 告警超时失效规则：告警长时间无响应自动失效
            InvalidationRule(
                rule_id="alert_timeout_invalidation",
                name="告警超时失效规则", 
                description="告警触发后6小时内无响应则自动失效",
                conditions=[
                    RuleCondition(
                        condition_id="alert_age_check",
                        condition_type=RuleConditionType.TIME_BASED,
                        operator=RuleOperator.GREATER_THAN,
                        field_path="occurrence_time",
                        expected_value=21600,  # 6小时 = 6*60*60秒
                        description="检查告警是否超过6小时"
                    ),
                    RuleCondition(
                        condition_id="no_response_check",
                        condition_type=RuleConditionType.EVENT_BASED,
                        operator=RuleOperator.NOT,
                        field_path="event_id",
                        expected_value={
                            "event_types": ["response_action"],
                            "states": ["valid"],
                        },
                        description="检查是否无响应行动"
                    )
                ],
                applicable_event_types=["alert_lifecycle"],
                priority=2,
                target_states=[TemporalValidityState.EXPIRED]
            ),
            
            # 恢复过程完成失效规则：恢复完成后自动失效
            InvalidationRule(
                rule_id="recovery_completion_invalidation",
                name="恢复完成失效规则",
                description="当检测到恢复验证成功时，恢复过程自动失效",
                conditions=[
                    RuleCondition(
                        condition_id="validation_success",
                        condition_type=RuleConditionType.EVENT_BASED,
                        operator=RuleOperator.EXISTS,
                        field_path="custom_properties.recovery_target",
                        expected_value={
                            "event_types": ["validation_check"],
                            "states": ["valid"],
                            "custom_properties.validation_result": "success"
                        },
                        description="检查恢复验证是否成功"
                    )
                ],
                applicable_event_types=["recovery_process"],
                priority=1
            ),
            
            # 指标恢复正常失效规则：关键指标恢复正常后失效相关事件
            InvalidationRule(
                rule_id="metrics_normalized_invalidation",
                name="指标恢复正常失效规则",
                description="关键性能指标恢复正常后，相关监控事件自动失效",
                conditions=[
                    RuleCondition(
                        condition_id="error_rate_normalized",
                        condition_type=RuleConditionType.METRIC_BASED,
                        operator=RuleOperator.LESS_THAN,
                        field_path="custom_properties.current_error_rate",
                        expected_value=0.01,  # 错误率低于1%
                        description="检查错误率是否已恢复正常"
                    ),
                    RuleCondition(
                        condition_id="metrics_stable_duration",
                        condition_type=RuleConditionType.TIME_BASED,
                        operator=RuleOperator.GREATER_THAN,
                        field_path="custom_properties.metrics_stable_since",
                        expected_value=300,  # 稳定5分钟
                        description="检查指标稳定时间"
                    )
                ],
                logical_operator=RuleOperator.AND,
                applicable_event_types=["impact_observation"],
                applicable_categories=["performance_monitoring"],
                priority=1
            ),
            
            # 事故关闭级联失效规则：事故关闭后级联失效所有相关事件
            InvalidationRule(
                rule_id="incident_closure_cascade_invalidation",
                name="事故关闭级联失效规则",
                description="事故正式关闭后，所有相关子事件自动失效",
                conditions=[
                    RuleCondition(
                        condition_id="incident_resolved",
                        condition_type=RuleConditionType.EVENT_BASED,
                        operator=RuleOperator.EXISTS,
                        field_path="custom_properties.incident_id",
                        expected_value={
                            "event_types": ["incident_resolution"],
                            "states": ["valid"],
                            "custom_properties.resolution_status": "closed"
                        },
                        description="检查事故是否已正式关闭"
                    )
                ],
                applicable_event_types=["fault_occurrence", "alert_lifecycle", "response_action"],
                priority=1,
                cooldown_seconds=60  # 1分钟冷却时间防止重复触发
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.rule_id] = rule
        
        logger.info(f"Loaded {len(default_rules)} default invalidation rules")
    
    def add_rule(self, rule: InvalidationRule):
        """添加自定义失效规则"""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added invalidation rule: {rule.rule_id}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除失效规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed invalidation rule: {rule_id}")
            return True
        return False
    
    def enable_rule(self, rule_id: str, enabled: bool = True):
        """启用/禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
            logger.info(f"Rule {rule_id} {'enabled' if enabled else 'disabled'}")
    
    async def evaluate_event_invalidation(self, 
                                        event_id: str,
                                        current_time: Optional[datetime] = None,
                                        external_data: Optional[Dict[str, Any]] = None) -> List[InvalidationRule]:
        """评估事件的失效规则"""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # 获取事件数据
        event_data = await self.temporal_db.get_temporal_event(event_id)
        if not event_data:
            logger.warning(f"Event not found: {event_id}")
            return []
        
        event_info = event_data.get('event', {})
        
        # 构建评估上下文
        context = RuleEvaluationContext(
            event_id=event_id,
            event_data=event_info,
            current_time=current_time,
            external_data=external_data
        )
        
        applicable_rules = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # 检查规则适用性
            if not self._is_rule_applicable(rule, event_info):
                continue
            
            # 检查冷却时间
            if not self._check_cooldown(rule.rule_id, current_time):
                continue
            
            # 评估规则条件
            if await self._evaluate_rule_conditions(rule, context):
                applicable_rules.append(rule)
        
        # 按优先级排序
        applicable_rules.sort(key=lambda r: r.priority)
        return applicable_rules
    
    def _is_rule_applicable(self, rule: InvalidationRule, event_data: Dict[str, Any]) -> bool:
        """检查规则是否适用于事件"""
        # 检查事件类型
        if rule.applicable_event_types:
            event_type = event_data.get('event_type', '')
            if event_type not in rule.applicable_event_types:
                return False
        
        # 检查事件分类
        if rule.applicable_categories:
            category = event_data.get('category', '')
            if category not in rule.applicable_categories:
                return False
        
        return True
    
    def _check_cooldown(self, rule_id: str, current_time: datetime) -> bool:
        """检查规则冷却时间"""
        if rule_id in self.cooldown_tracker:
            last_execution = self.cooldown_tracker[rule_id]
            rule = self.rules[rule_id]
            
            if rule.cooldown_seconds:
                time_diff = (current_time - last_execution).total_seconds()
                if time_diff < rule.cooldown_seconds:
                    return False
        
        return True
    
    async def _evaluate_rule_conditions(self, rule: InvalidationRule, context: RuleEvaluationContext) -> bool:
        """评估规则的所有条件"""
        if not rule.conditions:
            return False
        
        condition_results = []
        
        for condition in rule.conditions:
            # 获取对应的评估器
            evaluator = self.evaluators.get(condition.condition_type)
            if not evaluator:
                logger.warning(f"No evaluator found for condition type: {condition.condition_type}")
                condition_results.append(False)
                continue
            
            # 预处理条件（处理动态值）
            processed_condition = await self._preprocess_condition(condition, context)
            
            # 评估条件
            try:
                result = await evaluator.evaluate(processed_condition, context)
                condition_results.append(result)
                logger.debug(f"Condition {condition.condition_id} evaluated to: {result}")
            except Exception as e:
                logger.error(f"Error evaluating condition {condition.condition_id}: {e}")
                condition_results.append(False)
        
        # 根据逻辑操作符组合结果
        return self._combine_condition_results(condition_results, rule.logical_operator)
    
    async def _preprocess_condition(self, condition: RuleCondition, context: RuleEvaluationContext) -> RuleCondition:
        """预处理条件，处理动态值"""
        processed_condition = condition
        
        # 处理事件条件中的动态值
        if condition.condition_type == RuleConditionType.EVENT_BASED and isinstance(condition.expected_value, dict):
            expected_value = condition.expected_value.copy()
            
            # 动态设置服务名称等
            for key, value in expected_value.items():
                if value is None and key in context.event_data:
                    expected_value[key] = context.event_data[key]
                elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    # 处理模板变量，如 ${custom_properties.service_name}
                    var_path = value[2:-1]  # 去掉 ${ 和 }
                    var_value = self._get_nested_value(context.event_data, var_path)
                    if var_value is not None:
                        expected_value[key] = var_value
            
            processed_condition.expected_value = expected_value
        
        return processed_condition
    
    def _get_nested_value(self, data: Dict[str, Any], path: str):
        """获取嵌套字典值"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _combine_condition_results(self, results: List[bool], operator: RuleOperator) -> bool:
        """组合条件结果"""
        if not results:
            return False
        
        if operator == RuleOperator.AND:
            return all(results)
        elif operator == RuleOperator.OR:
            return any(results)
        elif operator == RuleOperator.NOT:
            return not results[0] if results else False
        else:
            # 默认为AND
            return all(results)
    
    async def execute_invalidation_rules(self, 
                                       event_id: str,
                                       applicable_rules: List[InvalidationRule],
                                       current_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """执行失效规则"""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        execution_results = []
        
        for rule in applicable_rules:
            if not rule.auto_execute:
                execution_results.append({
                    'rule_id': rule.rule_id,
                    'result': 'pending_manual_approval',
                    'timestamp': current_time.isoformat()
                })
                continue
            
            try:
                # 执行状态转换
                for target_state in rule.target_states:
                    success = await self.temporal_db.update_event_state(
                        event_id=event_id,
                        new_state=target_state.value,
                        trigger=f"invalidation_rule_{rule.rule_id}",
                        reason=f"Automatic invalidation via rule: {rule.name}",
                        automatic=True
                    )
                    
                    if success:
                        # 记录执行历史
                        self.rule_execution_history.append({
                            'rule_id': rule.rule_id,
                            'event_id': event_id,
                            'target_state': target_state.value,
                            'execution_time': current_time.isoformat(),
                            'result': 'success'
                        })
                        
                        # 更新冷却时间
                        if rule.cooldown_seconds:
                            self.cooldown_tracker[rule.rule_id] = current_time
                        
                        execution_results.append({
                            'rule_id': rule.rule_id,
                            'result': 'success',
                            'new_state': target_state.value,
                            'timestamp': current_time.isoformat()
                        })
                        
                        logger.info(f"Invalidation rule executed: {rule.rule_id} -> {event_id} -> {target_state.value}")
                    else:
                        execution_results.append({
                            'rule_id': rule.rule_id,
                            'result': 'failed',
                            'error': 'State update failed',
                            'timestamp': current_time.isoformat()
                        })
                        
            except Exception as e:
                logger.error(f"Error executing invalidation rule {rule.rule_id}: {e}")
                execution_results.append({
                    'rule_id': rule.rule_id,
                    'result': 'error',
                    'error': str(e),
                    'timestamp': current_time.isoformat()
                })
        
        return execution_results
    
    async def process_event_invalidation(self, 
                                       event_id: str,
                                       external_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """处理事件的完整失效流程"""
        current_time = datetime.now(timezone.utc)
        
        try:
            # 评估适用的失效规则
            applicable_rules = await self.evaluate_event_invalidation(
                event_id, current_time, external_data
            )
            
            if not applicable_rules:
                return {
                    'event_id': event_id,
                    'applicable_rules': 0,
                    'executions': [],
                    'timestamp': current_time.isoformat()
                }
            
            # 执行失效规则
            execution_results = await self.execute_invalidation_rules(
                event_id, applicable_rules, current_time
            )
            
            return {
                'event_id': event_id,
                'applicable_rules': len(applicable_rules),
                'rules_evaluated': [rule.rule_id for rule in applicable_rules],
                'executions': execution_results,
                'timestamp': current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing event invalidation: {e}")
            return {
                'event_id': event_id,
                'error': str(e),
                'timestamp': current_time.isoformat()
            }
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """获取规则执行统计"""
        if not self.rule_execution_history:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'rules_by_execution_count': {},
                'recent_executions': []
            }
        
        successful = sum(1 for exec in self.rule_execution_history if exec['result'] == 'success')
        failed = len(self.rule_execution_history) - successful
        
        # 按规则统计执行次数
        rule_counts = {}
        for exec in self.rule_execution_history:
            rule_id = exec['rule_id']
            rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
        
        return {
            'total_executions': len(self.rule_execution_history),
            'successful_executions': successful,
            'failed_executions': failed,
            'rules_by_execution_count': rule_counts,
            'recent_executions': self.rule_execution_history[-10:],  # 最近10次执行
            'total_rules': len(self.rules),
            'enabled_rules': sum(1 for rule in self.rules.values() if rule.enabled),
            'disabled_rules': sum(1 for rule in self.rules.values() if not rule.enabled)
        }