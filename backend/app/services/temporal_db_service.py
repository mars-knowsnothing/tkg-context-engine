# 时序数据库服务实现

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from ..services.falkordb_service import FalkorDBService
from ..models.temporal_schemas import TemporalEventNode, StateTransition, InvalidationCondition

logger = logging.getLogger(__name__)

class TemporalDatabaseService:
    """时序数据库服务 - 处理FalkorDB的时序扩展"""
    
    def __init__(self, falkordb_service: FalkorDBService):
        self.falkordb = falkordb_service
        self.initialized = False
    
    async def initialize_temporal_schema(self) -> bool:
        """初始化时序数据库Schema"""
        try:
            # 创建约束
            await self._create_constraints()
            
            # 创建索引
            await self._create_indexes()
            
            # 验证Schema
            await self._verify_schema()
            
            self.initialized = True
            logger.info("Temporal database schema initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize temporal schema: {e}")
            return False
    
    async def _create_constraints(self):
        """创建唯一性约束"""
        constraints = [
            "CREATE CONSTRAINT temporal_event_id_unique ON (event:TemporalEvent) ASSERT event.event_id IS UNIQUE",
            "CREATE CONSTRAINT invalidation_condition_id_unique ON (cond:InvalidationCondition) ASSERT cond.condition_id IS UNIQUE"
        ]
        
        for constraint in constraints:
            try:
                await self.falkordb.execute_query(constraint)
                logger.debug(f"Created constraint: {constraint}")
            except Exception as e:
                # 约束可能已存在，记录但不失败
                logger.debug(f"Constraint creation skipped (may exist): {e}")
    
    async def _create_indexes(self):
        """创建性能索引"""
        indexes = [
            # 时序事件基础索引
            "CREATE INDEX temporal_event_occurrence_time ON :TemporalEvent(occurrence_time)",
            "CREATE INDEX temporal_event_validity_range ON :TemporalEvent(validity_start, validity_end)", 
            "CREATE INDEX temporal_event_current_state ON :TemporalEvent(current_state)",
            "CREATE INDEX temporal_event_type_time ON :TemporalEvent(event_type, occurrence_time)",
            "CREATE INDEX temporal_event_category ON :TemporalEvent(category)",
            "CREATE INDEX temporal_event_severity ON :TemporalEvent(severity)",
            
            # 复合索引
            "CREATE INDEX temporal_event_state_validity ON :TemporalEvent(current_state, validity_start, validity_end)",
            "CREATE INDEX temporal_event_source_time ON :TemporalEvent(source_system, occurrence_time)",
            
            # 状态转换索引
            "CREATE INDEX state_transition_time ON :STATE_TRANSITION(transition_time)",
            "CREATE INDEX state_transition_states ON :STATE_TRANSITION(from_state, to_state)",
            "CREATE INDEX state_transition_trigger ON :STATE_TRANSITION(trigger_event)",
            
            # 失效条件索引
            "CREATE INDEX invalidation_condition_type ON :InvalidationCondition(condition_type)",
            "CREATE INDEX invalidation_condition_priority ON :InvalidationCondition(priority)",
            
            # 关系索引
            "CREATE INDEX temporal_relation_type ON :TEMPORAL_RELATION(relation_type)",
            "CREATE INDEX temporal_relation_confidence ON :TEMPORAL_RELATION(confidence)",
            "CREATE INDEX validation_dependency_type ON :DEPENDS_ON(dependency_type)"
        ]
        
        for index in indexes:
            try:
                await self.falkordb.execute_query(index)
                logger.debug(f"Created index: {index}")
            except Exception as e:
                # 索引可能已存在
                logger.debug(f"Index creation skipped (may exist): {e}")
    
    async def _verify_schema(self):
        """验证Schema是否正确创建"""
        try:
            # 验证约束
            constraints_query = "CALL db.constraints()"
            constraints_result = await self.falkordb.execute_query(constraints_query)
            logger.info(f"Active constraints: {len(constraints_result) if constraints_result else 0}")
            
            # 验证索引 
            indexes_query = "CALL db.indexes()"
            indexes_result = await self.falkordb.execute_query(indexes_query)
            logger.info(f"Active indexes: {len(indexes_result) if indexes_result else 0}")
        except Exception as e:
            logger.warning(f"Schema verification failed: {e}")
    
    async def create_temporal_event(self, event_dict: Dict[str, Any]) -> str:
        """创建时序事件节点"""
        if not self.initialized:
            await self.initialize_temporal_schema()
        
        # 构建事件节点属性
        import uuid
        event_id = str(uuid.uuid4())
        
        event_props = {
            'event_id': event_id,
            'event_type': event_dict.get('event_type', 'conditional'),
            'name': event_dict['name'],
            'description': event_dict['description'],
            'current_state': 'pending',
            'occurrence_time': event_dict.get('occurrence_time', datetime.now(timezone.utc).isoformat()),
            'detection_time': None,
            'confirmation_time': None,
            'validity_start': event_dict.get('validity_start', datetime.now(timezone.utc).isoformat()),
            'validity_end': event_dict.get('validity_end'),
            'confidence_score': 1.0,
            'certainty_level': 'HIGH',
            'severity': event_dict.get('severity', 'INFO'),
            'priority': event_dict.get('priority', 5),
            'category': event_dict['category'],
            'source_system': event_dict['source_system'],
            'responsible_team': None,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': None,
            'created_by': 'system',
            'tags': event_dict.get('tags', []),
            'impact_scope': {},
            'context_tags': [],
            'custom_properties': event_dict.get('custom_properties', {})
        }
        
        # 创建节点查询
        create_query = """
        CREATE (event:TemporalEvent $props)
        RETURN event.event_id as event_id
        """
        
        result = await self.falkordb.execute_query(create_query, {'props': event_props})
        
        if result and len(result) > 0:
            logger.info(f"Created temporal event: {event_id}")
            return event_id
        
        raise RuntimeError("Failed to create temporal event")
    
    async def get_temporal_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取时序事件"""
        query = """
        MATCH (event:TemporalEvent {event_id: $event_id})
        OPTIONAL MATCH (event)-[:HAS_INVALIDATION_CONDITION]->(condition:InvalidationCondition)
        OPTIONAL MATCH (event)-[transition:STATE_TRANSITION]->(event)
        OPTIONAL MATCH (event)-[dep:DEPENDS_ON]->(target:TemporalEvent)
        RETURN event,
               COLLECT(DISTINCT condition) as invalidation_conditions,
               COLLECT(DISTINCT transition) as state_transitions,
               COLLECT(DISTINCT {dependency: dep, target: target}) as dependencies
        """
        
        result = await self.falkordb.execute_query(query, {'event_id': event_id})
        
        if result and len(result) > 0:
            return result[0]
        return None
    
    async def get_events_at_time(self, 
                               timestamp: str,
                               event_types: Optional[List[str]] = None,
                               states: Optional[List[str]] = None,
                               categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """获取指定时间点的有效事件"""
        
        # 构建WHERE条件
        where_conditions = [
            "event.validity_start <= $timestamp",
            "(event.validity_end IS NULL OR event.validity_end >= $timestamp)"
        ]
        
        params = {'timestamp': timestamp}
        
        if event_types:
            where_conditions.append("event.event_type IN $event_types")
            params['event_types'] = event_types
        
        if states:
            where_conditions.append("event.current_state IN $states")
            params['states'] = states
            
        if categories:
            where_conditions.append("event.category IN $categories") 
            params['categories'] = categories
        
        query = f"""
        MATCH (event:TemporalEvent)
        WHERE {' AND '.join(where_conditions)}
        RETURN event
        ORDER BY event.occurrence_time DESC
        """
        
        return await self.falkordb.execute_query(query, params)
    
    async def get_state_transitions_in_range(self,
                                           start_time: str,
                                           end_time: str,
                                           event_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取时间范围内的状态转换"""
        
        if event_id:
            query = """
            MATCH (event:TemporalEvent {event_id: $event_id})-[t:STATE_TRANSITION]->(event)
            WHERE t.transition_time >= $start_time AND t.transition_time <= $end_time
            RETURN event, t
            ORDER BY t.transition_time ASC
            """
            params = {
                'event_id': event_id,
                'start_time': start_time,
                'end_time': end_time
            }
        else:
            query = """
            MATCH (event:TemporalEvent)-[t:STATE_TRANSITION]->(event)
            WHERE t.transition_time >= $start_time AND t.transition_time <= $end_time  
            RETURN event, t
            ORDER BY t.transition_time ASC
            """
            params = {
                'start_time': start_time,
                'end_time': end_time
            }
        
        return await self.falkordb.execute_query(query, params)
    
    async def update_event_state(self, event_id: str, 
                               new_state: str,
                               trigger: str,
                               reason: str,
                               automatic: bool = True) -> bool:
        """更新事件状态并记录转换"""
        
        # 获取当前状态
        current_query = """
        MATCH (event:TemporalEvent {event_id: $event_id})
        RETURN event.current_state as current_state
        """
        
        current_result = await self.falkordb.execute_query(current_query, {'event_id': event_id})
        if not current_result or len(current_result) == 0:
            return False
        
        current_state = current_result[0]['current_state']
        
        # 更新状态并创建转换记录
        update_query = """
        MATCH (event:TemporalEvent {event_id: $event_id})
        SET event.current_state = $new_state,
            event.updated_at = $updated_at
        CREATE (event)-[transition:STATE_TRANSITION {
            transition_id: $transition_id,
            from_state: $current_state,
            to_state: $new_state,
            transition_time: $transition_time,
            trigger_event: $trigger,
            reason: $reason,
            automatic: $automatic,
            confidence: 1.0
        }]->(event)
        RETURN transition.transition_id as transition_id
        """
        
        import uuid
        
        result = await self.falkordb.execute_query(update_query, {
            'event_id': event_id,
            'new_state': new_state,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'transition_id': str(uuid.uuid4()),
            'current_state': current_state,
            'transition_time': datetime.now(timezone.utc).isoformat(),
            'trigger': trigger,
            'reason': reason,
            'automatic': automatic
        })
        
        return bool(result)