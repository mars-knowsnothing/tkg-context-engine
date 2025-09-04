# 精确时点有效性查询引擎

import asyncio
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field

from ..models.temporal_schemas import (
    TemporalEventNode, 
    TemporalValidityState,
    StateTransition
)
from .temporal_db_service import TemporalDatabaseService

logger = logging.getLogger(__name__)

class QueryPrecision(str, Enum):
    """查询精度级别"""
    MILLISECOND = "millisecond"    # 毫秒级精度
    SECOND = "second"              # 秒级精度  
    MINUTE = "minute"              # 分钟级精度
    HOUR = "hour"                  # 小时级精度

class ValidationMethod(str, Enum):
    """有效性验证方法"""
    BASIC = "basic"                # 基础时间窗口验证
    STATE_AWARE = "state_aware"    # 状态感知验证
    FULL_LIFECYCLE = "full_lifecycle"  # 完整生命周期验证
    DEPENDENCY_AWARE = "dependency_aware"  # 依赖感知验证

@dataclass
class TimePointQueryOptions:
    """时点查询选项"""
    precision: QueryPrecision = QueryPrecision.SECOND
    validation_method: ValidationMethod = ValidationMethod.STATE_AWARE
    include_transitions: bool = False
    include_dependencies: bool = False
    include_invalidation_analysis: bool = False
    tolerance_seconds: int = 0  # 时间容差（秒）
    cache_results: bool = True
    max_results: Optional[int] = None

@dataclass
class TimePointValidityResult:
    """时点有效性查询结果"""
    query_time: datetime
    event_id: str
    event_name: str
    validity_state: TemporalValidityState
    is_valid: bool
    validity_confidence: float
    state_at_time: TemporalValidityState
    time_since_last_transition: float  # 秒
    time_until_next_transition: Optional[float]  # 秒，None表示无下次转换
    active_invalidation_conditions: List[str]
    dependency_status: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

class PreciseTimePointQueryEngine:
    """精确时点有效性查询引擎"""
    
    def __init__(self, temporal_db: TemporalDatabaseService):
        self.temporal_db = temporal_db
        self.query_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300  # 缓存5分钟
        
    def _generate_cache_key(self, query_time: datetime, options: TimePointQueryOptions, filters: Dict[str, Any]) -> str:
        """生成查询缓存键"""
        key_parts = [
            query_time.isoformat(),
            options.precision.value,
            options.validation_method.value,
            str(options.tolerance_seconds),
            str(hash(frozenset(filters.items()) if filters else frozenset()))
        ]
        return ":".join(key_parts)
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        if not cache_entry:
            return False
        
        cache_time = datetime.fromisoformat(cache_entry.get('cached_at', ''))
        return (datetime.now(timezone.utc) - cache_time).total_seconds() < self.cache_ttl
    
    async def query_events_at_time_point(self,
                                       query_time: datetime,
                                       options: TimePointQueryOptions = None,
                                       event_filters: Optional[Dict[str, Any]] = None) -> List[TimePointValidityResult]:
        """查询指定时间点的精确事件有效性"""
        
        if options is None:
            options = TimePointQueryOptions()
        
        # 标准化查询时间
        normalized_time = self._normalize_query_time(query_time, options.precision)
        
        # 检查缓存
        cache_key = self._generate_cache_key(normalized_time, options, event_filters or {})
        if options.cache_results and cache_key in self.query_cache:
            cache_entry = self.query_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                logger.debug(f"Returning cached result for time point query: {normalized_time}")
                return cache_entry['results']
        
        try:
            # 获取候选事件
            candidate_events = await self._get_candidate_events(normalized_time, event_filters, options)
            
            # 精确计算每个事件的有效性
            results = []
            for event_data in candidate_events:
                try:
                    validity_result = await self._compute_precise_validity(
                        event_data, normalized_time, options
                    )
                    if validity_result:
                        results.append(validity_result)
                except Exception as e:
                    logger.error(f"Error computing validity for event {event_data.get('event_id', 'unknown')}: {e}")
                    continue
            
            # 排序和限制结果
            results = self._sort_and_limit_results(results, options)
            
            # 缓存结果
            if options.cache_results:
                self.query_cache[cache_key] = {
                    'results': results,
                    'cached_at': datetime.now(timezone.utc).isoformat()
                }
            
            logger.info(f"Time point query returned {len(results)} valid events at {normalized_time}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute time point query: {e}")
            raise
    
    def _normalize_query_time(self, query_time: datetime, precision: QueryPrecision) -> datetime:
        """根据精度标准化查询时间"""
        if query_time.tzinfo is None:
            query_time = query_time.replace(tzinfo=timezone.utc)
        
        if precision == QueryPrecision.HOUR:
            return query_time.replace(minute=0, second=0, microsecond=0)
        elif precision == QueryPrecision.MINUTE:
            return query_time.replace(second=0, microsecond=0)
        elif precision == QueryPrecision.SECOND:
            return query_time.replace(microsecond=0)
        else:  # MILLISECOND
            return query_time
    
    async def _get_candidate_events(self,
                                  query_time: datetime,
                                  filters: Optional[Dict[str, Any]],
                                  options: TimePointQueryOptions) -> List[Dict[str, Any]]:
        """获取候选事件"""
        
        # 计算查询时间窗口（考虑容差）
        time_start = query_time - timedelta(seconds=options.tolerance_seconds)
        time_end = query_time + timedelta(seconds=options.tolerance_seconds)
        
        # 构建查询条件
        where_conditions = [
            "(event.validity_start <= $query_end)",
            "(event.validity_end IS NULL OR event.validity_end >= $query_start)"
        ]
        
        params = {
            'query_start': time_start.isoformat(),
            'query_end': time_end.isoformat()
        }
        
        # 添加过滤条件
        if filters:
            if filters.get('event_types'):
                where_conditions.append("event.event_type IN $event_types")
                params['event_types'] = filters['event_types']
            
            if filters.get('categories'):
                where_conditions.append("event.category IN $categories")
                params['categories'] = filters['categories']
            
            if filters.get('source_systems'):
                where_conditions.append("event.source_system IN $source_systems")
                params['source_systems'] = filters['source_systems']
        
        # 构建完整查询
        query = f"""
        MATCH (event:TemporalEvent)
        WHERE {' AND '.join(where_conditions)}
        RETURN event,
               [(event)-[t:STATE_TRANSITION]->(event) | t] as transitions,
               [(event)-[:HAS_INVALIDATION_CONDITION]->(cond) | cond] as conditions,
               [(event)-[dep:DEPENDS_ON]->(target) | {{dependency: dep, target: target}}] as dependencies
        ORDER BY event.occurrence_time DESC
        """
        
        if options.max_results:
            query += f" LIMIT {options.max_results * 2}"  # 获取更多候选，后续精确过滤
        
        results = await self.temporal_db.falkordb.execute_query(query, params)
        return results
    
    async def _compute_precise_validity(self,
                                      event_data: Dict[str, Any],
                                      query_time: datetime,
                                      options: TimePointQueryOptions) -> Optional[TimePointValidityResult]:
        """计算事件在指定时间的精确有效性"""
        
        try:
            event_info = event_data['event']
            transitions = event_data.get('transitions', [])
            conditions = event_data.get('conditions', [])
            dependencies = event_data.get('dependencies', [])
            
            event_id = event_info['event_id']
            
            # 1. 基础时间窗口验证
            if not self._is_in_basic_time_window(event_info, query_time):
                return None
            
            # 2. 根据验证方法进行详细验证
            if options.validation_method == ValidationMethod.BASIC:
                validity_state, is_valid = self._basic_validity_check(event_info, query_time)
            elif options.validation_method == ValidationMethod.STATE_AWARE:
                validity_state, is_valid = await self._state_aware_validity_check(
                    event_info, transitions, query_time
                )
            elif options.validation_method == ValidationMethod.FULL_LIFECYCLE:
                validity_state, is_valid = await self._full_lifecycle_validity_check(
                    event_info, transitions, conditions, query_time
                )
            elif options.validation_method == ValidationMethod.DEPENDENCY_AWARE:
                validity_state, is_valid = await self._dependency_aware_validity_check(
                    event_info, transitions, dependencies, query_time
                )
            else:
                validity_state, is_valid = self._basic_validity_check(event_info, query_time)
            
            # 3. 计算置信度
            confidence = await self._calculate_validity_confidence(
                event_info, transitions, conditions, query_time, options
            )
            
            # 4. 分析状态转换时间
            time_since_last, time_until_next = await self._analyze_transition_timing(
                transitions, query_time
            )
            
            # 5. 分析活跃的失效条件
            active_conditions = await self._analyze_active_invalidation_conditions(
                conditions, query_time, options
            )
            
            # 6. 分析依赖状态
            dependency_status = await self._analyze_dependency_status(
                dependencies, query_time, options
            )
            
            # 构建结果
            result = TimePointValidityResult(
                query_time=query_time,
                event_id=event_id,
                event_name=event_info.get('name', 'Unknown'),
                validity_state=validity_state,
                is_valid=is_valid,
                validity_confidence=confidence,
                state_at_time=validity_state,
                time_since_last_transition=time_since_last,
                time_until_next_transition=time_until_next,
                active_invalidation_conditions=active_conditions,
                dependency_status=dependency_status,
                metadata={
                    'event_type': event_info.get('event_type'),
                    'category': event_info.get('category'),
                    'occurrence_time': event_info.get('occurrence_time'),
                    'validity_start': event_info.get('validity_start'),
                    'validity_end': event_info.get('validity_end'),
                    'validation_method': options.validation_method.value,
                    'query_precision': options.precision.value
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error computing precise validity: {e}")
            return None
    
    def _is_in_basic_time_window(self, event_info: Dict[str, Any], query_time: datetime) -> bool:
        """基础时间窗口检查"""
        try:
            validity_start = datetime.fromisoformat(event_info['validity_start'].replace('Z', '+00:00'))
            validity_end = None
            
            if event_info.get('validity_end'):
                validity_end = datetime.fromisoformat(event_info['validity_end'].replace('Z', '+00:00'))
            
            # 检查是否在有效时间窗口内
            if query_time < validity_start:
                return False
            
            if validity_end and query_time > validity_end:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in basic time window check: {e}")
            return False
    
    def _basic_validity_check(self, event_info: Dict[str, Any], query_time: datetime) -> Tuple[TemporalValidityState, bool]:
        """基础有效性检查"""
        current_state_str = event_info.get('current_state', 'pending')
        
        try:
            current_state = TemporalValidityState(current_state_str)
        except ValueError:
            current_state = TemporalValidityState.PENDING
        
        is_valid = current_state in [TemporalValidityState.VALID, TemporalValidityState.PENDING]
        
        return current_state, is_valid
    
    async def _state_aware_validity_check(self,
                                        event_info: Dict[str, Any],
                                        transitions: List[Dict[str, Any]],
                                        query_time: datetime) -> Tuple[TemporalValidityState, bool]:
        """状态感知有效性检查"""
        
        # 如果没有状态转换历史，使用当前状态
        if not transitions:
            return self._basic_validity_check(event_info, query_time)
        
        # 按时间排序转换
        sorted_transitions = sorted(
            transitions,
            key=lambda t: datetime.fromisoformat(t.get('transition_time', '').replace('Z', '+00:00'))
        )
        
        # 找到查询时间点的状态
        state_at_time = TemporalValidityState.PENDING  # 默认初始状态
        
        for transition in sorted_transitions:
            try:
                transition_time = datetime.fromisoformat(transition['transition_time'].replace('Z', '+00:00'))
                if transition_time <= query_time:
                    state_at_time = TemporalValidityState(transition['to_state'])
                else:
                    break
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid transition data: {e}")
                continue
        
        is_valid = state_at_time in [TemporalValidityState.VALID, TemporalValidityState.PENDING]
        
        return state_at_time, is_valid
    
    async def _full_lifecycle_validity_check(self,
                                           event_info: Dict[str, Any],
                                           transitions: List[Dict[str, Any]],
                                           conditions: List[Dict[str, Any]],
                                           query_time: datetime) -> Tuple[TemporalValidityState, bool]:
        """完整生命周期有效性检查"""
        
        # 首先进行状态感知检查
        state_at_time, basic_valid = await self._state_aware_validity_check(
            event_info, transitions, query_time
        )
        
        # 如果基础检查失败，直接返回
        if not basic_valid:
            return state_at_time, False
        
        # 检查失效条件
        for condition in conditions:
            if await self._is_invalidation_condition_active(condition, query_time):
                return TemporalValidityState.INVALID, False
        
        return state_at_time, basic_valid
    
    async def _dependency_aware_validity_check(self,
                                             event_info: Dict[str, Any],
                                             transitions: List[Dict[str, Any]],
                                             dependencies: List[Dict[str, Any]],
                                             query_time: datetime) -> Tuple[TemporalValidityState, bool]:
        """依赖感知有效性检查"""
        
        # 首先进行完整生命周期检查
        state_at_time, basic_valid = await self._full_lifecycle_validity_check(
            event_info, transitions, [], query_time
        )
        
        # 检查依赖关系
        for dep_info in dependencies:
            dependency = dep_info.get('dependency', {})
            target = dep_info.get('target', {})
            
            if dependency.get('required', False):
                target_valid = await self._check_dependency_target_validity(target, query_time)
                if not target_valid:
                    return TemporalValidityState.INVALID, False
        
        return state_at_time, basic_valid
    
    async def _calculate_validity_confidence(self,
                                           event_info: Dict[str, Any],
                                           transitions: List[Dict[str, Any]],
                                           conditions: List[Dict[str, Any]],
                                           query_time: datetime,
                                           options: TimePointQueryOptions) -> float:
        """计算有效性置信度"""
        
        confidence = 1.0
        
        # 基于时间距离的置信度调整
        try:
            occurrence_time = datetime.fromisoformat(event_info['occurrence_time'].replace('Z', '+00:00'))
            time_diff = abs((query_time - occurrence_time).total_seconds())
            
            # 时间距离越远，置信度越低
            if time_diff > 86400:  # 超过1天
                confidence *= 0.9
            elif time_diff > 3600:  # 超过1小时
                confidence *= 0.95
        except:
            confidence *= 0.8
        
        # 基于状态转换数量的置信度调整
        if len(transitions) > 0:
            # 有转换历史，置信度更高
            confidence *= 1.1
        else:
            # 无转换历史，置信度降低
            confidence *= 0.9
        
        # 基于失效条件的置信度调整
        active_conditions_count = sum(
            1 for cond in conditions
            if self._is_invalidation_condition_potentially_active(cond, query_time)
        )
        
        if active_conditions_count > 0:
            confidence *= (1 - 0.1 * active_conditions_count)
        
        # 确保置信度在合理范围内
        return max(0.0, min(1.0, confidence))
    
    async def _analyze_transition_timing(self,
                                       transitions: List[Dict[str, Any]],
                                       query_time: datetime) -> Tuple[float, Optional[float]]:
        """分析状态转换时间"""
        
        if not transitions:
            return float('inf'), None
        
        sorted_transitions = sorted(
            transitions,
            key=lambda t: datetime.fromisoformat(t.get('transition_time', '').replace('Z', '+00:00'))
        )
        
        time_since_last = float('inf')
        time_until_next = None
        
        for transition in sorted_transitions:
            try:
                transition_time = datetime.fromisoformat(transition['transition_time'].replace('Z', '+00:00'))
                
                if transition_time <= query_time:
                    # 过去的转换
                    time_since_last = (query_time - transition_time).total_seconds()
                else:
                    # 未来的转换
                    if time_until_next is None:
                        time_until_next = (transition_time - query_time).total_seconds()
                    break
                    
            except Exception as e:
                logger.warning(f"Error analyzing transition timing: {e}")
                continue
        
        return time_since_last, time_until_next
    
    async def _analyze_active_invalidation_conditions(self,
                                                    conditions: List[Dict[str, Any]],
                                                    query_time: datetime,
                                                    options: TimePointQueryOptions) -> List[str]:
        """分析活跃的失效条件"""
        
        active_conditions = []
        
        if not options.include_invalidation_analysis:
            return active_conditions
        
        for condition in conditions:
            if await self._is_invalidation_condition_active(condition, query_time):
                active_conditions.append(condition.get('condition_id', 'unknown'))
        
        return active_conditions
    
    async def _analyze_dependency_status(self,
                                       dependencies: List[Dict[str, Any]],
                                       query_time: datetime,
                                       options: TimePointQueryOptions) -> Dict[str, Any]:
        """分析依赖状态"""
        
        dependency_status = {
            'total_dependencies': len(dependencies),
            'satisfied_dependencies': 0,
            'failed_dependencies': 0,
            'pending_dependencies': 0
        }
        
        if not options.include_dependencies:
            return dependency_status
        
        for dep_info in dependencies:
            target = dep_info.get('target', {})
            
            try:
                target_valid = await self._check_dependency_target_validity(target, query_time)
                if target_valid:
                    dependency_status['satisfied_dependencies'] += 1
                else:
                    dependency_status['failed_dependencies'] += 1
            except:
                dependency_status['pending_dependencies'] += 1
        
        return dependency_status
    
    async def _is_invalidation_condition_active(self, condition: Dict[str, Any], query_time: datetime) -> bool:
        """检查失效条件是否激活"""
        # 简化实现 - 实际应该根据条件类型进行复杂评估
        condition_type = condition.get('condition_type', '')
        
        if condition_type == 'time_based':
            # 时间类条件检查
            return True  # 简化
        elif condition_type == 'dependency_based':
            # 依赖类条件检查
            return False  # 简化
        
        return False
    
    def _is_invalidation_condition_potentially_active(self, condition: Dict[str, Any], query_time: datetime) -> bool:
        """检查失效条件是否可能激活（用于置信度计算）"""
        # 简化实现
        return condition.get('auto_check', False)
    
    async def _check_dependency_target_validity(self, target_event: Dict[str, Any], query_time: datetime) -> bool:
        """检查依赖目标事件的有效性"""
        # 简化实现 - 实际应该递归检查目标事件
        target_id = target_event.get('event_id')
        if not target_id:
            return False
        
        try:
            # 快速检查目标事件状态
            target_data = await self.temporal_db.get_temporal_event(target_id)
            if not target_data:
                return False
            
            target_info = target_data['event']
            target_state = TemporalValidityState(target_info.get('current_state', 'pending'))
            
            return target_state == TemporalValidityState.VALID
            
        except:
            return False
    
    def _sort_and_limit_results(self,
                              results: List[TimePointValidityResult],
                              options: TimePointQueryOptions) -> List[TimePointValidityResult]:
        """排序和限制结果"""
        
        # 按置信度和有效性排序
        results.sort(key=lambda r: (r.is_valid, r.validity_confidence), reverse=True)
        
        # 限制结果数量
        if options.max_results and len(results) > options.max_results:
            results = results[:options.max_results]
        
        return results
    
    def clear_cache(self):
        """清空查询缓存"""
        self.query_cache.clear()
        logger.info("Time point query cache cleared")
    
    async def batch_query_time_points(self,
                                    time_points: List[datetime],
                                    options: TimePointQueryOptions = None,
                                    event_filters: Optional[Dict[str, Any]] = None) -> Dict[datetime, List[TimePointValidityResult]]:
        """批量查询多个时间点的事件有效性"""
        
        if options is None:
            options = TimePointQueryOptions()
        
        results = {}
        
        # 并发执行查询
        tasks = []
        for time_point in time_points:
            task = self.query_events_at_time_point(time_point, options, event_filters)
            tasks.append((time_point, task))
        
        # 等待所有查询完成
        for time_point, task in tasks:
            try:
                query_results = await task
                results[time_point] = query_results
            except Exception as e:
                logger.error(f"Batch query failed for time point {time_point}: {e}")
                results[time_point] = []
        
        logger.info(f"Batch query completed for {len(time_points)} time points")
        return results