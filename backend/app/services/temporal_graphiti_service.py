# 状态转换引擎集成服务

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from ..services.graphiti_service import GraphitiService
from ..services.temporal_db_service import TemporalDatabaseService
from ..services.state_transition_engine import StateTransitionEngine, TransitionResult
from ..models.temporal_schemas import TemporalValidityState

logger = logging.getLogger(__name__)

class TemporalGraphitiService:
    """增强的Graphiti服务，集成状态转换引擎"""
    
    def __init__(self):
        self.graphiti_service = None
        self.temporal_db_service = None
        self.transition_engine = None
        self.initialized = False
    
    async def initialize(self):
        """初始化所有服务组件"""
        try:
            # 初始化原有的Graphiti服务
            self.graphiti_service = GraphitiService()
            await self.graphiti_service.initialize()
            
            # 初始化时序数据库服务
            self.temporal_db_service = TemporalDatabaseService(self.graphiti_service.falkordb)
            await self.temporal_db_service.initialize_temporal_schema()
            
            # 初始化状态转换引擎
            self.transition_engine = StateTransitionEngine(self.temporal_db_service)
            
            # 启动自动化监控
            await self.transition_engine.start_automated_monitoring(check_interval=30)
            
            self.initialized = True
            logger.info("TemporalGraphitiService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize TemporalGraphitiService: {e}")
            raise RuntimeError(f"TemporalGraphitiService initialization failed: {e}")
    
    async def close(self):
        """关闭所有服务"""
        if self.transition_engine:
            await self.transition_engine.stop_monitoring()
        
        if self.graphiti_service:
            await self.graphiti_service.close()
    
    # 兼容原有GraphitiService接口
    async def create_node(self, name: str, content: str, node_type: str = 'entity', properties: Optional[Dict[str, Any]] = None) -> str:
        """创建节点（兼容模式）"""
        if not self.initialized:
            await self.initialize()
        
        return await self.graphiti_service.create_node(name, content, node_type, properties)
    
    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点（兼容模式）"""
        if not self.initialized:
            await self.initialize()
        
        return await self.graphiti_service.get_node_by_id(node_id)
    
    async def update_node(self, node_id: str, **kwargs) -> bool:
        """更新节点（增强模式）"""
        if not self.initialized:
            await self.initialize()
        
        # 执行原有的更新逻辑
        result = await self.graphiti_service.update_node(node_id, **kwargs)
        
        # 如果节点是时序事件，触发状态转换检查
        await self._check_node_state_transitions(node_id, "node_update", kwargs)
        
        return result
    
    async def delete_node(self, node_id: str) -> bool:
        """删除节点（兼容模式）"""
        if not self.initialized:
            await self.initialize()
        
        return await self.graphiti_service.delete_node(node_id)
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索节点（兼容模式）"""
        if not self.initialized:
            await self.initialize()
        
        return await self.graphiti_service.search_nodes(query, limit)
    
    # 新增时序功能
    async def create_temporal_event(self, event_data: Dict[str, Any]) -> str:
        """创建时序事件"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 使用时序数据库服务创建事件
            from ..models.temporal_schemas import TemporalEventNode, TemporalEventType, EventValidityContext
            
            # 构建时序事件对象 (简化版本)
            temporal_event = TemporalEventNode(
                name=event_data['name'],
                event_type=TemporalEventType(event_data.get('event_type', 'conditional')),
                description=event_data.get('description', ''),
                validity_context=EventValidityContext(
                    occurrence_time=datetime.fromisoformat(event_data.get('occurrence_time', datetime.now(timezone.utc).isoformat())),
                    validity_start=datetime.fromisoformat(event_data.get('validity_start', datetime.now(timezone.utc).isoformat()))
                ),
                category=event_data.get('category', 'general'),
                source_system=event_data.get('source_system', 'system'),
                custom_properties=event_data.get('custom_properties', {})
            )
            
            # 创建事件
            event_id = await self.temporal_db_service.create_temporal_event(temporal_event)
            
            # 触发初始状态转换检查
            await self._check_node_state_transitions(event_id, "event_creation", event_data)
            
            logger.info(f"Created temporal event: {event_id}")
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to create temporal event: {e}")
            raise
    
    async def get_temporal_events_at_time(self, 
                                        timestamp: str,
                                        filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """获取指定时间点的有效事件"""
        if not self.initialized:
            await self.initialize()
        
        try:
            events = await self.temporal_db_service.get_events_at_time(
                timestamp=timestamp,
                event_types=filters.get('event_types') if filters else None,
                states=filters.get('states') if filters else None,
                categories=filters.get('categories') if filters else None
            )
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get temporal events at time: {e}")
            return []
    
    async def trigger_event_state_transition(self, 
                                           event_id: str, 
                                           trigger_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """手动触发事件状态转换"""
        if not self.initialized:
            await self.initialize()
        
        try:
            results = await self.transition_engine.process_event_transitions(
                event_id=event_id,
                trigger_source="manual_api_call",
                trigger_data=trigger_data
            )
            
            return {
                'event_id': event_id,
                'transition_results': [result.value for result in results],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'trigger_data': trigger_data
            }
            
        except Exception as e:
            logger.error(f"Failed to trigger state transition: {e}")
            return {
                'event_id': event_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def manual_state_change(self, 
                                event_id: str, 
                                target_state: str,
                                reason: str,
                                operator: str = "system") -> Dict[str, Any]:
        """手动改变事件状态"""
        if not self.initialized:
            await self.initialize()
        
        try:
            target_state_enum = TemporalValidityState(target_state)
            
            result = await self.transition_engine.manual_trigger_transition(
                event_id=event_id,
                target_state=target_state_enum,
                reason=reason,
                operator=operator
            )
            
            return {
                'event_id': event_id,
                'new_state': target_state,
                'result': result.value,
                'reason': reason,
                'operator': operator,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to manually change state: {e}")
            return {
                'event_id': event_id,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_event_lifecycle(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取事件完整生命周期"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 获取事件基础信息
            event_data = await self.temporal_db_service.get_temporal_event(event_id)
            if not event_data:
                return None
            
            # 获取状态转换历史
            transitions = await self.temporal_db_service.get_state_transitions_in_range(
                start_time="1900-01-01T00:00:00Z",
                end_time=datetime.now(timezone.utc).isoformat(),
                event_id=event_id
            )
            
            return {
                'event_id': event_id,
                'current_state': event_data['event']['current_state'],
                'state_transitions': transitions,
                'invalidation_conditions': event_data.get('invalidation_conditions', []),
                'dependencies': event_data.get('dependencies', []),
                'lifecycle_analysis': await self._analyze_event_lifecycle(event_data, transitions)
            }
            
        except Exception as e:
            logger.error(f"Failed to get event lifecycle: {e}")
            return None
    
    async def get_transition_statistics(self) -> Dict[str, Any]:
        """获取状态转换统计信息"""
        if not self.initialized:
            await self.initialize()
        
        engine_stats = self.transition_engine.get_transition_statistics()
        
        # 添加数据库统计
        graph_stats = await self.graphiti_service.get_graph_stats()
        
        return {
            'transition_engine': engine_stats,
            'graph_database': graph_stats,
            'active_monitors': len(self.transition_engine.active_monitors),
            'transition_rules': len(self.transition_engine.transition_rules),
            'condition_evaluators': len(self.transition_engine.condition_evaluators)
        }
    
    async def _check_node_state_transitions(self, 
                                          node_id: str, 
                                          trigger_source: str, 
                                          context_data: Dict[str, Any]):
        """检查节点的状态转换（内部方法）"""
        try:
            # 检查节点是否为时序事件
            node_data = await self.temporal_db_service.get_temporal_event(node_id)
            if not node_data:
                # 不是时序事件，跳过
                return
            
            # 触发状态转换检查
            await self.transition_engine.process_event_transitions(
                event_id=node_id,
                trigger_source=trigger_source,
                trigger_data=context_data
            )
            
        except Exception as e:
            # 状态转换失败不应影响主要的节点操作
            logger.warning(f"State transition check failed for node {node_id}: {e}")
    
    async def _analyze_event_lifecycle(self, 
                                     event_data: Dict[str, Any], 
                                     transitions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析事件生命周期（内部方法）"""
        try:
            if not transitions:
                return {'status': 'no_transitions', 'duration_seconds': 0}
            
            # 计算生命周期指标
            first_transition = min(transitions, key=lambda t: t.get('transition_time', ''))
            last_transition = max(transitions, key=lambda t: t.get('transition_time', ''))
            
            first_time = datetime.fromisoformat(first_transition['transition_time'].replace('Z', '+00:00'))
            last_time = datetime.fromisoformat(last_transition['transition_time'].replace('Z', '+00:00'))
            
            duration = (last_time - first_time).total_seconds()
            
            # 分析状态分布
            state_distribution = {}
            for transition in transitions:
                to_state = transition.get('to_state', 'unknown')
                state_distribution[to_state] = state_distribution.get(to_state, 0) + 1
            
            return {
                'status': 'analyzed',
                'total_transitions': len(transitions),
                'duration_seconds': duration,
                'first_transition': first_transition['transition_time'],
                'last_transition': last_transition['transition_time'],
                'state_distribution': state_distribution,
                'automatic_transitions': sum(1 for t in transitions if t.get('automatic', False)),
                'manual_transitions': sum(1 for t in transitions if not t.get('automatic', False))
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze event lifecycle: {e}")
            return {'status': 'analysis_failed', 'error': str(e)}

# 全局服务实例
temporal_graphiti_service = TemporalGraphitiService()