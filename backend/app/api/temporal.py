from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field
from ..models.schemas import (
    TemporalQueryRequest, TemporalQueryResult, TimeInterval, 
    TemporalValidityState, KnowledgeNodeResponse, RelationResponse, BaseResponse
)
from ..services.graphiti_service import GraphitiService
from ..services.temporal_graphiti_service import temporal_graphiti_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# === Enhanced Request Models for New Temporal Features ===

class TemporalEventCreate(BaseModel):
    """时序事件创建请求模型"""
    name: str = Field(..., description="事件名称")
    description: str = Field(..., description="事件描述") 
    event_type: str = Field(..., description="事件类型")
    category: str = Field(..., description="事件分类")
    source_system: str = Field(..., description="来源系统")
    occurrence_time: Optional[str] = Field(None, description="发生时间(ISO格式)")
    validity_start: Optional[str] = Field(None, description="有效期开始时间")
    validity_end: Optional[str] = Field(None, description="有效期结束时间")
    severity: Optional[str] = Field("INFO", description="严重程度")
    priority: Optional[int] = Field(5, description="优先级(1-10)")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    custom_properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="自定义属性")

class StateTransitionRequest(BaseModel):
    """状态转换请求模型"""
    trigger_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="触发数据")
    reason: Optional[str] = Field(None, description="转换原因")

class ManualStateChangeRequest(BaseModel):
    """手动状态变更请求模型"""
    target_state: str = Field(..., description="目标状态")
    reason: str = Field(..., description="变更原因") 
    operator: str = Field(..., description="操作员")

class TimePointQueryRequest(BaseModel):
    """时点查询请求模型"""
    query_time: str = Field(..., description="查询时间点(ISO格式)")
    event_types: Optional[List[str]] = Field(None, description="事件类型过滤")
    categories: Optional[List[str]] = Field(None, description="分类过滤")
    states: Optional[List[str]] = Field(None, description="状态过滤")
    include_transitions: Optional[bool] = Field(False, description="是否包含状态转换历史")

class TimeRangeQueryRequest(BaseModel):
    """时间范围查询请求模型"""
    start_time: str = Field(..., description="开始时间(ISO格式)")
    end_time: str = Field(..., description="结束时间(ISO格式)")
    event_types: Optional[List[str]] = Field(None, description="事件类型过滤")
    categories: Optional[List[str]] = Field(None, description="分类过滤")
    states: Optional[List[str]] = Field(None, description="状态过滤")
    include_lifecycle: Optional[bool] = Field(False, description="是否包含生命周期分析")

def get_graphiti_service(request: Request) -> GraphitiService:
    return request.app.state.graphiti_service

def _normalize_node_type(raw_type: str) -> str:
    """Normalize node type from various formats to valid enum values"""
    if not isinstance(raw_type, str):
        return 'entity'
    
    # Handle enum-like strings (e.g., "NodeType.ENTITY", "nodetype.entity" -> "entity")
    type_str = raw_type.split('.')[-1].lower() if '.' in raw_type else raw_type.lower()
    # Remove any prefix like "nodetype"
    node_type = type_str.replace('nodetype', '').strip('.')
    
    if node_type not in ['entity', 'event', 'concept', 'episode']:
        node_type = 'entity'
    
    return node_type

@router.post("/query", response_model=TemporalQueryResult)
async def temporal_query(
    query_req: TemporalQueryRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Execute a temporal query on the knowledge graph"""
    try:
        logger.info(f"Temporal query: {query_req.query}, at_time: {query_req.at_time}")
        
        # Get all nodes first
        all_nodes = await graphiti_service.search_nodes(query_req.query, limit=query_req.limit * 2)
        
        # Apply temporal filtering
        filtered_nodes = []
        validity_counts = {"valid": 0, "invalid": 0, "pending": 0, "expired": 0}
        
        query_time = query_req.at_time or datetime.utcnow()
        
        for node in all_nodes:
            # Create time interval from node properties
            valid_time = None
            if 'valid_from' in node.get('properties', {}) or 'valid_until' in node.get('properties', {}):
                valid_from_str = node.get('properties', {}).get('valid_from')
                valid_until_str = node.get('properties', {}).get('valid_until')
                
                start_time = None
                end_time = None
                
                if valid_from_str:
                    try:
                        start_time = datetime.fromisoformat(valid_from_str.replace('Z', '+00:00'))
                    except:
                        pass
                        
                if valid_until_str:
                    try:
                        end_time = datetime.fromisoformat(valid_until_str.replace('Z', '+00:00'))
                    except:
                        pass
                        
                if start_time or end_time:
                    valid_time = TimeInterval(start_time=start_time, end_time=end_time)
            
            # Determine validity state
            validity_state = TemporalValidityState.VALID
            if valid_time:
                validity_state = valid_time.get_validity_state(query_time)
                if query_req.at_time:  # Point-in-time query
                    is_valid_at_time = valid_time.is_valid_at(query_req.at_time)
                    if not is_valid_at_time:
                        validity_state = TemporalValidityState.INVALID
            
            # Apply validity filter
            if query_req.validity_filter and validity_state != query_req.validity_filter:
                continue
            
            validity_counts[validity_state.value] += 1
            
            # Create enhanced node response
            enhanced_node = KnowledgeNodeResponse(
                id=node['id'],
                name=node['name'],
                type=_normalize_node_type(node.get('type', 'entity')),
                content=node['content'],
                properties=node.get('properties', {}),
                created_at=node['created_at'] if isinstance(node['created_at'], datetime) 
                    else datetime.fromisoformat(node['created_at'].replace('Z', '+00:00')),
                updated_at=node.get('updated_at'),
                valid_time=valid_time,
                validity_state=validity_state
            )
            
            filtered_nodes.append(enhanced_node)
        
        # Limit results
        filtered_nodes = filtered_nodes[:query_req.limit]
        
        # Generate temporal explanation
        temporal_scope = "Current time"
        if query_req.at_time:
            temporal_scope = f"At {query_req.at_time.strftime('%Y-%m-%d %H:%M:%S')}"
        elif query_req.time_range:
            temporal_scope = f"From {query_req.time_range.start_time} to {query_req.time_range.end_time}"
        
        explanation = f"Temporal query '{query_req.query}' executed for {temporal_scope}. "
        explanation += f"Found {len(filtered_nodes)} relevant nodes. "
        explanation += f"Validity breakdown: {validity_counts}"
        
        return TemporalQueryResult(
            nodes=filtered_nodes,
            relations=[],  # TODO: Add temporal relation filtering
            confidence=0.9,
            explanation=explanation,
            temporal_scope=temporal_scope,
            validity_summary=validity_counts
        )
        
    except Exception as e:
        logger.error(f"Temporal query error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/validity-states")
async def get_validity_states(
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Get count of nodes by validity state"""
    try:
        all_nodes = await graphiti_service.search_nodes("", limit=1000)  # Get all nodes
        
        validity_counts = {"valid": 0, "invalid": 0, "pending": 0, "expired": 0, "unknown": 0}
        current_time = datetime.utcnow()
        
        for node in all_nodes:
            # Check for temporal properties
            properties = node.get('properties', {})
            valid_from_str = properties.get('valid_from')
            valid_until_str = properties.get('valid_until')
            
            if not valid_from_str and not valid_until_str:
                validity_counts["valid"] += 1  # Default to valid if no temporal info
                continue
                
            try:
                start_time = None
                end_time = None
                
                if valid_from_str:
                    start_time = datetime.fromisoformat(valid_from_str.replace('Z', '+00:00'))
                if valid_until_str:
                    end_time = datetime.fromisoformat(valid_until_str.replace('Z', '+00:00'))
                
                time_interval = TimeInterval(start_time=start_time, end_time=end_time)
                validity_state = time_interval.get_validity_state(current_time)
                validity_counts[validity_state.value] += 1
                
            except Exception:
                validity_counts["unknown"] += 1
        
        return {
            "total_nodes": len(all_nodes),
            "validity_breakdown": validity_counts,
            "query_time": current_time
        }
        
    except Exception as e:
        logger.error(f"Validity states error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/nodes/set-validity")
async def set_node_validity(
    node_id: str,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Set temporal validity for a node"""
    try:
        # Get existing node
        node = await graphiti_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Update properties with temporal info
        properties = node.get('properties', {})
        if valid_from:
            properties['valid_from'] = valid_from.isoformat()
        if valid_until:
            properties['valid_until'] = valid_until.isoformat()
        
        # Update the node
        await graphiti_service.update_node(
            node_id=node_id,
            properties=properties
        )
        
        return {
            "message": "Node validity updated successfully",
            "node_id": node_id,
            "valid_from": valid_from,
            "valid_until": valid_until
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set validity error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/demo/create-temporal-data")
async def create_temporal_demo_data(
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Create demo data to showcase temporal features"""
    try:
        current_time = datetime.utcnow()
        
        # Create nodes with different temporal states
        demo_nodes = [
            {
                "name": "Current Employee: John Doe",
                "content": "Software engineer currently employed at the company",
                "type": "entity",
                "properties": {
                    "valid_from": (current_time - timedelta(days=365)).isoformat(),
                    "employment_status": "active"
                }
            },
            {
                "name": "Former Employee: Jane Smith", 
                "content": "Former project manager who left the company",
                "type": "entity",
                "properties": {
                    "valid_from": (current_time - timedelta(days=730)).isoformat(),
                    "valid_until": (current_time - timedelta(days=30)).isoformat(),
                    "employment_status": "terminated"
                }
            },
            {
                "name": "Future Project: AI Initiative",
                "content": "Upcoming AI project scheduled to start next month",
                "type": "event",
                "properties": {
                    "valid_from": (current_time + timedelta(days=30)).isoformat(),
                    "valid_until": (current_time + timedelta(days=365)).isoformat(),
                    "project_status": "planned"
                }
            },
            {
                "name": "Expired Policy: Remote Work v1.0",
                "content": "Old remote work policy that was replaced",
                "type": "concept",
                "properties": {
                    "valid_from": (current_time - timedelta(days=1000)).isoformat(), 
                    "valid_until": (current_time - timedelta(days=90)).isoformat(),
                    "policy_version": "1.0"
                }
            }
        ]
        
        created_nodes = []
        for node_data in demo_nodes:
            node_id = await graphiti_service.create_node(
                name=node_data["name"],
                content=node_data["content"],
                node_type=node_data["type"],
                properties=node_data["properties"]
            )
            created_nodes.append({"id": node_id, "name": node_data["name"]})
        
        return {
            "message": "Temporal demo data created successfully",
            "created_nodes": created_nodes,
            "demo_queries": [
                "Show me current employees",
                "What was valid 6 months ago?", 
                "Show me future projects",
                "List all expired policies"
            ]
        }
        
    except Exception as e:
        logger.error(f"Demo data creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === Enhanced Temporal API Endpoints ===

@router.post("/events", response_model=BaseResponse)
async def create_temporal_event(event_data: TemporalEventCreate):
    """创建时序事件"""
    try:
        # 初始化服务
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 转换为服务期望的格式
        event_dict = event_data.dict()
        
        # 设置默认时间
        if not event_dict.get('occurrence_time'):
            event_dict['occurrence_time'] = datetime.now(timezone.utc).isoformat()
        if not event_dict.get('validity_start'):
            event_dict['validity_start'] = event_dict['occurrence_time']
        
        # 创建事件
        event_id = await temporal_graphiti_service.create_temporal_event(event_dict)
        
        logger.info(f"Created temporal event via API: {event_id}")
        
        return BaseResponse(
            success=True,
            message="时序事件创建成功",
            data={"event_id": event_id}
        )
        
    except Exception as e:
        logger.error(f"Failed to create temporal event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events/{event_id}", response_model=BaseResponse)
async def get_temporal_event(event_id: str):
    """获取指定时序事件"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 获取事件数据
        event_data = await temporal_graphiti_service.temporal_db_service.get_temporal_event(event_id)
        
        if not event_data:
            raise HTTPException(status_code=404, detail="事件未找到")
        
        return BaseResponse(
            success=True,
            data=event_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get temporal event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/events/{event_id}/transition", response_model=BaseResponse)
async def trigger_state_transition(event_id: str, request: StateTransitionRequest):
    """触发事件状态转换"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 执行状态转换
        result = await temporal_graphiti_service.trigger_event_state_transition(
            event_id, 
            request.trigger_data
        )
        
        return BaseResponse(
            success=True,
            message="状态转换触发成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger state transition for {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/events/{event_id}/state", response_model=BaseResponse)
async def manual_state_change(event_id: str, request: ManualStateChangeRequest):
    """手动变更事件状态"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 执行手动状态变更
        result = await temporal_graphiti_service.manual_state_change(
            event_id=event_id,
            target_state=request.target_state,
            reason=request.reason,
            operator=request.operator
        )
        
        return BaseResponse(
            success=True,
            message="状态变更成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Failed to manually change state for {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events/{event_id}/lifecycle", response_model=BaseResponse)
async def get_event_lifecycle(event_id: str):
    """获取事件完整生命周期"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 获取生命周期数据
        lifecycle = await temporal_graphiti_service.get_event_lifecycle(event_id)
        
        if not lifecycle:
            raise HTTPException(status_code=404, detail="事件生命周期未找到")
        
        return BaseResponse(
            success=True,
            data=lifecycle
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get event lifecycle {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/time-point", response_model=BaseResponse)
async def query_events_at_time_point(request: TimePointQueryRequest):
    """查询指定时间点的有效事件"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 构建过滤器
        filters = {}
        if request.event_types:
            filters['event_types'] = request.event_types
        if request.categories:
            filters['categories'] = request.categories
        if request.states:
            filters['states'] = request.states
        
        # 执行查询
        events = await temporal_graphiti_service.get_temporal_events_at_time(
            request.query_time, 
            filters if filters else None
        )
        
        # 如果需要包含状态转换历史
        if request.include_transitions:
            enhanced_events = []
            for event in events:
                event_id = event.get('event_id')
                if event_id:
                    lifecycle = await temporal_graphiti_service.get_event_lifecycle(event_id)
                    if lifecycle:
                        event['transitions'] = lifecycle.get('state_transitions', [])
                enhanced_events.append(event)
            events = enhanced_events
        
        return BaseResponse(
            success=True,
            message=f"查询到 {len(events)} 个在时间点 {request.query_time} 有效的事件",
            data={
                'query_time': request.query_time,
                'filters': filters,
                'events': events,
                'count': len(events)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to query events at time point: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/time-range", response_model=BaseResponse)
async def query_events_in_time_range(request: TimeRangeQueryRequest):
    """查询时间范围内的事件状态转换"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 获取时间范围内的状态转换
        transitions = await temporal_graphiti_service.temporal_db_service.get_state_transitions_in_range(
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        # 如果指定了过滤条件，进一步过滤
        if request.event_types or request.categories or request.states:
            filtered_transitions = []
            for transition in transitions:
                event_data = transition.get('event', {})
                
                # 检查事件类型
                if request.event_types and event_data.get('event_type') not in request.event_types:
                    continue
                    
                # 检查分类
                if request.categories and event_data.get('category') not in request.categories:
                    continue
                    
                # 检查状态
                if request.states and transition.get('t', {}).get('to_state') not in request.states:
                    continue
                
                filtered_transitions.append(transition)
            
            transitions = filtered_transitions
        
        # 如果需要生命周期分析
        lifecycle_analysis = {}
        if request.include_lifecycle and transitions:
            # 按事件分组分析
            events_analysis = {}
            for transition in transitions:
                event_id = transition.get('event', {}).get('event_id')
                if event_id and event_id not in events_analysis:
                    lifecycle = await temporal_graphiti_service.get_event_lifecycle(event_id)
                    if lifecycle:
                        events_analysis[event_id] = lifecycle['lifecycle_analysis']
            
            lifecycle_analysis = events_analysis
        
        return BaseResponse(
            success=True,
            message=f"查询到时间范围 {request.start_time} 至 {request.end_time} 内的 {len(transitions)} 个状态转换",
            data={
                'start_time': request.start_time,
                'end_time': request.end_time,
                'transitions': transitions,
                'count': len(transitions),
                'lifecycle_analysis': lifecycle_analysis if request.include_lifecycle else None
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to query events in time range: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics/enhanced", response_model=BaseResponse)
async def get_enhanced_statistics():
    """获取增强的时序统计信息"""
    try:
        if not temporal_graphiti_service.initialized:
            await temporal_graphiti_service.initialize()
        
        # 获取统计信息
        stats = await temporal_graphiti_service.get_transition_statistics()
        
        # 获取失效规则统计
        invalidation_engine = temporal_graphiti_service.transition_engine.invalidation_engine
        invalidation_stats = invalidation_engine.get_rule_statistics()
        
        return BaseResponse(
            success=True,
            data={
                'transition_engine': stats['transition_engine'],
                'graph_database': stats['graph_database'],
                'invalidation_engine': invalidation_stats,
                'active_monitors': stats['active_monitors'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get enhanced statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/enhanced", response_model=BaseResponse)
async def enhanced_temporal_health_check():
    """增强的时序服务健康检查"""
    try:
        health_status = {
            'temporal_service_initialized': temporal_graphiti_service.initialized,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if temporal_graphiti_service.initialized:
            # 获取基础统计信息
            stats = await temporal_graphiti_service.get_transition_statistics()
            health_status.update({
                'total_transitions': stats['transition_engine']['total_transitions'],
                'active_monitors': stats['active_monitors'],
                'graph_nodes': stats['graph_database']['nodes'],
                'graph_relationships': stats['graph_database']['relationships'],
                'invalidation_rules': len(temporal_graphiti_service.transition_engine.invalidation_engine.rules),
                'transition_rules': len(temporal_graphiti_service.transition_engine.transition_rules)
            })
        
        return BaseResponse(
            success=True,
            message="增强时序服务运行正常",
            data=health_status
        )
        
    except Exception as e:
        logger.error(f"Enhanced temporal health check failed: {e}")
        return BaseResponse(
            success=False,
            message="增强时序服务健康检查失败",
            data={'error': str(e)}
        )