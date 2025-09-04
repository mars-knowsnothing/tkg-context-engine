"""
统一事件API - 基于可观测性设计的事件管理端点
支持事件创建、查询、聚合和生命周期管理
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Union, Dict, Any
from datetime import datetime, timedelta

from ..models.schemas import (
    UnifiedEvent, UnifiedEventCreate, UnifiedEventResponse, 
    EventFilter, EventAggregation, EventType, EventSeverity, 
    TemporalValidityState, DetectionMethod, ComponentType,
    BaseResponse
)
from ..services.graphiti_service import GraphitiService
from ..services.falkordb_service import FalkorDBService
from ..services.event_normalization_service import EventNormalizationService, DataSource
from ..services.causality_engine import CausalityOrchestrator
from ..services.state_machine_service import StateManager
from ..services.event_deduplication_service import EventDeduplicationService, DeduplicationStrategy

router = APIRouter(prefix="/api/events", tags=["统一事件管理"])

# 依赖注入
def get_graphiti_service() -> GraphitiService:
    return GraphitiService()

def get_falkordb_service() -> FalkorDBService:
    return FalkorDBService()

def get_normalization_service() -> EventNormalizationService:
    return EventNormalizationService()

def get_causality_orchestrator() -> CausalityOrchestrator:
    return CausalityOrchestrator()

def get_state_manager() -> StateManager:
    return StateManager()

def get_deduplication_service() -> EventDeduplicationService:
    return EventDeduplicationService()

# =============================================================================
# 原始事件接入和标准化
# =============================================================================

@router.post("/ingest/{source}", response_model=BaseResponse, summary="接入原始事件数据")
async def ingest_raw_events(
    source: str,
    raw_events: Union[Dict[str, Any], List[Dict[str, Any]]],
    normalization_service: EventNormalizationService = Depends(get_normalization_service),
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
    falkor_service: FalkorDBService = Depends(get_falkordb_service),
    state_manager: StateManager = Depends(get_state_manager)
):
    """
    接入原始事件数据并进行标准化处理
    
    支持的数据源:
    - prometheus: Prometheus告警数据
    - k8s: Kubernetes事件数据  
    - loki: Loki日志数据
    - manual: 手动输入数据
    """
    try:
        # 验证数据源
        try:
            data_source = DataSource(source)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的数据源: {source}")
        
        # 转换为列表格式
        raw_event_list = raw_events if isinstance(raw_events, list) else [raw_events]
        
        # 批量标准化
        normalized_events = normalization_service.batch_normalize_events(raw_event_list, data_source)
        
        if not normalized_events:
            return BaseResponse(
                success=False,
                message="所有原始事件标准化失败",
                data={"processed": 0, "failed": len(raw_event_list)}
            )
        
        # 批量创建事件
        created_events = []
        failed_count = 0
        state_updates = []
        
        for normalized_event in normalized_events:
            try:
                # 创建统一事件
                unified_event = UnifiedEvent(**normalized_event.dict())
                
                # 存储到图数据库
                node_data = {
                    "name": f"{unified_event.event_type}_{unified_event.component}",
                    "type": "event",
                    "content": unified_event.message,
                    "properties": {
                        **unified_event.dict(),
                        "timestamp": unified_event.timestamp.isoformat(),
                        "observed_start": unified_event.observed_start.isoformat() if unified_event.observed_start else None,
                        "observed_end": unified_event.observed_end.isoformat() if unified_event.observed_end else None
                    }
                }
                
                # 使用Graphiti服务创建节点
                result = await graphiti_service.create_node(
                    name=node_data["name"],
                    content=node_data["content"],
                    node_type="event",
                    properties=node_data["properties"]
                )
                
                # 存储到FalkorDB
                await store_event_to_falkor(unified_event, falkor_service)
                
                # 处理状态机事件
                state_result = await state_manager.process_event(unified_event)
                if state_result:
                    state_updates.append({
                        "event_id": unified_event.event_id,
                        "state_result": state_result
                    })
                
                created_events.append({
                    "event_id": unified_event.event_id,
                    "graphiti_node_id": result.get("id"),
                    "fingerprint": unified_event.fingerprint,
                    "state_updated": state_result is not None
                })
                
            except Exception as e:
                print(f"创建事件失败: {e}")
                failed_count += 1
        
        return BaseResponse(
            success=True,
            message=f"批量接入完成: 成功 {len(created_events)}, 失败 {failed_count}, 状态更新 {len(state_updates)}",
            data={
                "source": source,
                "processed": len(raw_event_list),
                "created": len(created_events),
                "failed": failed_count,
                "state_updates_count": len(state_updates),
                "events": created_events,
                "state_updates": state_updates
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量接入失败: {str(e)}")

@router.get("/sources", response_model=BaseResponse, summary="获取支持的数据源")
async def get_supported_sources(
    normalization_service: EventNormalizationService = Depends(get_normalization_service)
):
    """获取支持的数据源列表和示例格式"""
    
    sources_info = {
        "prometheus": {
            "description": "Prometheus告警数据",
            "example": {
                "alertname": "HighErrorRate",
                "labels": {
                    "service": "order-service",
                    "severity": "critical",
                    "namespace": "prod"
                },
                "annotations": {
                    "summary": "订单服务错误率过高",
                    "runbook_url": "http://runbook.example.com"
                },
                "startsAt": "2025-09-04T08:15:30Z"
            }
        },
        "k8s": {
            "description": "Kubernetes事件数据",
            "example": {
                "kind": "Event",
                "reason": "CrashLoopBackOff",
                "message": "Back-off restarting failed container",
                "type": "Warning",
                "involvedObject": {
                    "kind": "Pod",
                    "name": "order-service-abc123",
                    "namespace": "prod"
                },
                "firstTimestamp": "2025-09-04T08:15:30Z"
            }
        },
        "loki": {
            "description": "Loki日志数据",
            "example": {
                "message": "ERROR: Database connection timeout",
                "timestamp": "2025-09-04T08:15:30Z",
                "level": "error",
                "service": "order-service",
                "namespace": "prod"
            }
        }
    }
    
    return BaseResponse(
        success=True,
        message="数据源信息获取成功",
        data={
            "supported_sources": normalization_service.get_supported_sources(),
            "source_details": sources_info
        }
    )

@router.post("/normalize/preview", response_model=BaseResponse, summary="预览事件标准化结果")
async def preview_normalization(
    source: str,
    raw_event: Dict[str, Any],
    normalization_service: EventNormalizationService = Depends(get_normalization_service)
):
    """预览原始事件的标准化结果，不实际创建事件"""
    try:
        # 验证数据源
        try:
            data_source = DataSource(source)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的数据源: {source}")
        
        # 执行标准化
        normalized_event = normalization_service.normalize_event(raw_event, data_source)
        
        if not normalized_event:
            return BaseResponse(
                success=False,
                message="事件标准化失败",
                data={"raw_event": raw_event}
            )
        
        return BaseResponse(
            success=True,
            message="事件标准化预览成功",
            data={
                "source": source,
                "raw_event": raw_event,
                "normalized_event": normalized_event.dict()
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标准化预览失败: {str(e)}")

# =============================================================================
# 因果关系推理
# =============================================================================

@router.post("/analyze/causality", response_model=BaseResponse, summary="分析事件因果关系")
async def analyze_event_causality(
    event_ids: Optional[List[str]] = None,
    time_range_minutes: int = 30,
    min_confidence: float = 0.5,
    causality_orchestrator: CausalityOrchestrator = Depends(get_causality_orchestrator),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """
    分析事件间的因果关系
    
    支持功能:
    - 基于拓扑的因果推理
    - 基于Trace的因果推理  
    - 基于故障模式库的因果推理
    - 多引擎并行处理和结果融合
    """
    try:
        # 获取分析事件
        if event_ids:
            # 基于指定事件ID获取事件
            events = await get_events_by_ids(event_ids, falkor_service)
        else:
            # 获取最近时间范围内的事件
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=time_range_minutes)
            events = await get_events_by_time_range(start_time, end_time, falkor_service)
        
        if len(events) < 2:
            return BaseResponse(
                success=False,
                message="需要至少2个事件才能进行因果分析",
                data={"event_count": len(events)}
            )
        
        # 设置置信度阈值
        causality_orchestrator.set_confidence_threshold(min_confidence)
        
        # 执行因果推理
        causality_relations = await causality_orchestrator.infer_causality_relations(events)
        
        # 生成图关系格式
        graph_relations = await causality_orchestrator.create_graph_relations(causality_relations)
        
        # 统计信息
        causality_stats = {
            "total_events_analyzed": len(events),
            "causality_relations_found": len(causality_relations),
            "confidence_distribution": _calculate_confidence_distribution(causality_relations),
            "causality_types": _calculate_causality_types(causality_relations),
            "methods_used": _calculate_methods_used(causality_relations)
        }
        
        return BaseResponse(
            success=True,
            message=f"因果分析完成: 发现 {len(causality_relations)} 个因果关系",
            data={
                "causality_relations": [
                    {
                        "cause_event_id": r.cause_event_id,
                        "effect_event_id": r.effect_event_id,
                        "causality_type": r.causality_type.value,
                        "confidence": r.confidence,
                        "method": r.method.value,
                        "time_gap_seconds": r.time_gap_seconds,
                        "evidence": r.evidence
                    }
                    for r in causality_relations
                ],
                "graph_relations": [gr.dict() for gr in graph_relations],
                "statistics": causality_stats
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"因果分析失败: {str(e)}")

@router.get("/causality/engines", response_model=BaseResponse, summary="获取因果推理引擎状态")
async def get_causality_engines_status(
    causality_orchestrator: CausalityOrchestrator = Depends(get_causality_orchestrator)
):
    """获取因果推理引擎状态和配置"""
    try:
        status = causality_orchestrator.get_engine_status()
        
        return BaseResponse(
            success=True,
            message="因果推理引擎状态获取成功",
            data=status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取引擎状态失败: {str(e)}")

@router.post("/causality/engines/{engine_name}/toggle", response_model=BaseResponse, summary="切换推理引擎状态")
async def toggle_causality_engine(
    engine_name: str,
    enable: bool,
    causality_orchestrator: CausalityOrchestrator = Depends(get_causality_orchestrator)
):
    """启用或禁用指定的因果推理引擎"""
    try:
        if enable:
            causality_orchestrator.enable_engine(engine_name)
            action = "启用"
        else:
            causality_orchestrator.disable_engine(engine_name)
            action = "禁用"
        
        return BaseResponse(
            success=True,
            message=f"推理引擎 {engine_name} 已{action}",
            data={"engine_name": engine_name, "enabled": enable}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换引擎状态失败: {str(e)}")

@router.get("/causality/topology", response_model=BaseResponse, summary="获取服务拓扑信息")
async def get_service_topology(
    causality_orchestrator: CausalityOrchestrator = Depends(get_causality_orchestrator)
):
    """获取用于因果推理的服务拓扑信息"""
    try:
        # 从拓扑引擎获取服务拓扑
        topology_engine = None
        for engine in causality_orchestrator.engines:
            if engine.name == "Topology_Causality_Engine":
                topology_engine = engine
                break
        
        if not topology_engine:
            return BaseResponse(
                success=False,
                message="拓扑推理引擎未找到",
                data={}
            )
        
        topology_data = {
            "services": []
        }
        
        for service_name, topology in topology_engine.service_topology.items():
            topology_data["services"].append({
                "service_name": service_name,
                "dependencies": topology.dependencies,
                "dependents": topology.dependents,
                "component_type": topology.component_type
            })
        
        return BaseResponse(
            success=True,
            message="服务拓扑信息获取成功",
            data=topology_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务拓扑失败: {str(e)}")

# =============================================================================
# 事件CRUD操作 
# =============================================================================

@router.post("/", response_model=BaseResponse, summary="创建统一事件")
async def create_event(
    event: UnifiedEventCreate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
    falkor_service: FalkorDBService = Depends(get_falkordb_service),
    state_manager: StateManager = Depends(get_state_manager),
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """
    创建新的统一事件
    
    支持功能:
    - 自动生成事件指纹和ID
    - 时效性验证
    - 事件去重检查
    - 存储到图数据库
    """
    try:
        # 创建统一事件对象 - 补充缺失字段
        event_data = event.dict()
        
        # 生成event_id (UUID)
        if not event_data.get("event_id"):
            import uuid
            event_data["event_id"] = str(uuid.uuid4())
        
        # 生成fingerprint使用智能去重服务
        if not event_data.get("fingerprint"):
            # 设置默认值
            if not event_data.get("timestamp"):
                event_data["timestamp"] = datetime.utcnow()
            
            # 确保枚举类型正确
            if isinstance(event_data.get("event_type"), str):
                event_data["event_type"] = EventType(event_data["event_type"])
            if isinstance(event_data.get("severity"), str):
                event_data["severity"] = EventSeverity(event_data["severity"])
            if isinstance(event_data.get("detection_method"), str):
                event_data["detection_method"] = DetectionMethod(event_data["detection_method"])
            if isinstance(event_data.get("component_type"), str):
                event_data["component_type"] = ComponentType(event_data["component_type"])
            
            # 创建UnifiedEvent对象用于指纹生成
            temp_event = UnifiedEvent(**event_data)
            event_data["fingerprint"] = deduplication_service.generate_fingerprint(
                temp_event, DeduplicationStrategy.FUZZY_MATCH
            )
        
        # 设置默认timestamp (如果之前没有设置)
        if not event_data.get("timestamp"):
            event_data["timestamp"] = datetime.utcnow()
        
        # 再次确保枚举类型正确 (以防之前没有设置)
        if isinstance(event_data.get("event_type"), str):
            event_data["event_type"] = EventType(event_data["event_type"])
        if isinstance(event_data.get("severity"), str):
            event_data["severity"] = EventSeverity(event_data["severity"])  
        if isinstance(event_data.get("detection_method"), str):
            event_data["detection_method"] = DetectionMethod(event_data["detection_method"])
        if isinstance(event_data.get("component_type"), str):
            event_data["component_type"] = ComponentType(event_data["component_type"])
            
        unified_event = UnifiedEvent(**event_data)
        
        # 智能去重处理
        is_duplicate, event_group = deduplication_service.deduplicate_event(
            unified_event, DeduplicationStrategy.FUZZY_MATCH
        )
        
        if is_duplicate:
            # 找到重复事件，返回聚合信息
            return BaseResponse(
                success=True,
                message=f"事件已聚合到现有分组 (第{event_group.occurrence_count}次出现)",
                data={
                    "event_id": unified_event.event_id,
                    "fingerprint": unified_event.fingerprint,
                    "is_duplicate": True,
                    "group_info": {
                        "fingerprint": event_group.fingerprint,
                        "occurrence_count": event_group.occurrence_count,
                        "first_seen": event_group.first_seen.isoformat(),
                        "last_seen": event_group.last_seen.isoformat(),
                        "canonical_event_id": event_group.canonical_event.event_id
                    },
                    "deduplication_strategy": "fuzzy_match"
                }
            )
        
        # 创建图节点
        node_data = {
            "name": f"{unified_event.event_type}_{unified_event.component}",
            "type": "event",
            "content": unified_event.message,
            "properties": {
                "event_id": unified_event.event_id,
                "event_type": unified_event.event_type,
                "severity": unified_event.severity,
                "confidence": unified_event.confidence,
                "source": unified_event.source,
                "detection_method": unified_event.detection_method,
                "fingerprint": unified_event.fingerprint,
                "trace_id": unified_event.trace_id,
                "correlation_id": unified_event.correlation_id,
                "service": unified_event.service,
                "component": unified_event.component,
                "component_type": unified_event.component_type,
                "namespace": unified_event.namespace,
                "cluster": unified_event.cluster,
                "region": unified_event.region,
                "owner": unified_event.owner,
                "metrics": unified_event.metrics,
                "evidence_refs": unified_event.evidence_refs,
                "ttl_sec": unified_event.ttl_sec,
                "timestamp": unified_event.timestamp.isoformat(),
                "observed_start": unified_event.observed_start.isoformat() if unified_event.observed_start else None,
                "observed_end": unified_event.observed_end.isoformat() if unified_event.observed_end else None
            }
        }
        
        # 使用Graphiti服务创建节点
        result = await graphiti_service.create_node(
            name=node_data["name"],
            content=node_data["content"],
            node_type="event",
            properties=node_data["properties"]
        )
        
        # 同时存储到FalkorDB以支持高性能查询
        await store_event_to_falkor(unified_event, falkor_service)
        
        # 处理状态机事件
        state_result = await state_manager.process_event(unified_event)
        
        return BaseResponse(
            success=True,
            message="统一事件创建成功",
            data={
                "event_id": unified_event.event_id,
                "graphiti_node_id": result.get("id"),
                "fingerprint": unified_event.fingerprint,
                "state_machine_result": state_result
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建事件失败: {str(e)}")

@router.get("/", response_model=BaseResponse, summary="查询统一事件")
async def query_events(
    event_types: Optional[List[EventType]] = Query(None, description="事件类型过滤"),
    severities: Optional[List[EventSeverity]] = Query(None, description="严重程度过滤"),
    services: Optional[List[str]] = Query(None, description="服务名过滤"),
    components: Optional[List[str]] = Query(None, description="组件名过滤"),
    namespaces: Optional[List[str]] = Query(None, description="命名空间过滤"),
    search_query: Optional[str] = Query(None, description="搜索关键词"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    validity_states: Optional[List[TemporalValidityState]] = Query(None, description="有效性状态过滤"),
    limit: int = Query(20, ge=1, le=1000, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """
    查询统一事件
    
    支持功能:
    - 多维度过滤
    - 时间范围查询
    - 有效性状态过滤
    - 全文搜索
    - 分页
    """
    try:
        # 构建过滤条件
        event_filter = EventFilter(
            event_types=event_types,
            severities=severities, 
            services=services,
            components=components,
            namespaces=namespaces,
            search_query=search_query,
            time_range=None,  # 将通过start_time和end_time构建
            validity_states=validity_states,
            limit=limit,
            offset=offset
        )
        
        # 执行查询
        events = await query_events_from_falkor(event_filter, start_time, end_time, falkor_service)
        
        return BaseResponse(
            success=True,
            message=f"查询到 {len(events)} 个事件",
            data={
                "events": events,
                "filter": event_filter.dict(),
                "total_count": len(events)  # 简化实现，实际应该返回总数
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询事件失败: {str(e)}")

@router.get("/aggregation", response_model=BaseResponse, summary="事件聚合统计")
async def get_event_aggregation(
    start_time: Optional[datetime] = Query(None, description="统计开始时间"),
    end_time: Optional[datetime] = Query(None, description="统计结束时间"),
    group_by: str = Query("severity", description="分组字段: severity|type|service|component"),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """
    获取事件聚合统计信息
    
    支持功能:
    - 时间范围统计
    - 多维度分组
    - 趋势分析
    """
    try:
        aggregation = await get_event_stats(start_time, end_time, group_by, falkor_service)
        
        return BaseResponse(
            success=True,
            message="聚合统计完成",
            data=aggregation
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聚合统计失败: {str(e)}")

@router.get("/types", response_model=BaseResponse, summary="获取事件类型枚举")
async def get_event_types():
    """获取所有可用的事件类型"""
    return BaseResponse(
        success=True,
        message="事件类型枚举获取成功",
        data={
            "event_types": [{"value": t.value, "name": t.value} for t in EventType],
            "severities": [{"value": s.value, "name": s.value} for s in EventSeverity],
            "detection_methods": [{"value": d.value, "name": d.value} for d in DetectionMethod],
            "component_types": [{"value": c.value, "name": c.value} for c in ComponentType],
            "validity_states": [{"value": v.value, "name": v.value} for v in TemporalValidityState]
        }
    )

# =============================================================================
# 事件去重管理
# =============================================================================

@router.get("/deduplication/stats", response_model=BaseResponse, summary="获取去重统计信息")
async def get_deduplication_stats(
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """获取事件去重系统的统计信息"""
    try:
        stats = deduplication_service.get_deduplication_stats()
        
        return BaseResponse(
            success=True,
            message="去重统计信息获取成功",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取去重统计失败: {str(e)}")

@router.get("/deduplication/groups", response_model=BaseResponse, summary="获取事件分组")
async def get_event_groups(
    min_frequency: int = Query(1, ge=1, description="最小频次过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """获取事件去重分组列表"""
    try:
        # 获取高频事件分组
        frequent_groups = deduplication_service.get_event_groups_by_frequency(min_frequency)
        
        # 限制返回数量并转换为可序列化格式
        limited_groups = frequent_groups[:limit]
        
        groups_data = []
        for group in limited_groups:
            group_data = {
                "fingerprint": group.fingerprint,
                "occurrence_count": group.occurrence_count,
                "first_seen": group.first_seen.isoformat(),
                "last_seen": group.last_seen.isoformat(),
                "canonical_event": {
                    "event_id": group.canonical_event.event_id,
                    "event_type": group.canonical_event.event_type.value,
                    "severity": group.canonical_event.severity.value,
                    "service": group.canonical_event.service,
                    "component": group.canonical_event.component,
                    "message": group.canonical_event.message[:200] + "..." if len(group.canonical_event.message) > 200 else group.canonical_event.message
                },
                "aggregated_data": group.aggregated_data
            }
            groups_data.append(group_data)
        
        return BaseResponse(
            success=True,
            message=f"获取到 {len(groups_data)} 个事件分组",
            data={
                "groups": groups_data,
                "total_groups": len(frequent_groups),
                "returned_count": len(groups_data)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件分组失败: {str(e)}")

@router.post("/deduplication/analyze", response_model=BaseResponse, summary="分析事件相似度")
async def analyze_event_similarity(
    event1_id: str,
    event2_id: str,
    falkor_service: FalkorDBService = Depends(get_falkordb_service),
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """分析两个事件之间的相似度"""
    try:
        # 从数据库获取事件
        events1 = await get_events_by_ids([event1_id], falkor_service)
        events2 = await get_events_by_ids([event2_id], falkor_service)
        
        if not events1 or not events2:
            raise HTTPException(status_code=404, detail="未找到指定的事件")
        
        event1, event2 = events1[0], events2[0]
        
        # 计算相似度
        similarity = deduplication_service.calculate_similarity(event1, event2)
        
        # 生成不同策略的指纹
        fingerprints = {}
        for strategy in DeduplicationStrategy:
            try:
                fp1 = deduplication_service.generate_fingerprint(event1, strategy)
                fp2 = deduplication_service.generate_fingerprint(event2, strategy)
                fingerprints[strategy.value] = {
                    "event1_fingerprint": fp1,
                    "event2_fingerprint": fp2,
                    "match": fp1 == fp2
                }
            except Exception:
                fingerprints[strategy.value] = {"error": "无法生成指纹"}
        
        return BaseResponse(
            success=True,
            message="事件相似度分析完成",
            data={
                "event1_id": event1_id,
                "event2_id": event2_id,
                "similarity_score": similarity,
                "similarity_level": (
                    "高" if similarity >= 0.8 else
                    "中" if similarity >= 0.6 else
                    "低"
                ),
                "fingerprint_analysis": fingerprints,
                "events_summary": {
                    "event1": {
                        "service": event1.service,
                        "component": event1.component,
                        "event_type": event1.event_type.value,
                        "message": event1.message[:100] + "..." if len(event1.message) > 100 else event1.message
                    },
                    "event2": {
                        "service": event2.service,
                        "component": event2.component,
                        "event_type": event2.event_type.value,
                        "message": event2.message[:100] + "..." if len(event2.message) > 100 else event2.message
                    }
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"相似度分析失败: {str(e)}")

@router.post("/deduplication/cleanup", response_model=BaseResponse, summary="清理过期事件分组")
async def cleanup_event_groups(
    ttl_hours: int = Query(24, ge=1, le=168, description="过期时间（小时）"),
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """清理过期的事件分组"""
    try:
        cleaned_count = deduplication_service.cleanup_old_groups(ttl_hours)
        
        return BaseResponse(
            success=True,
            message=f"清理完成，删除了 {cleaned_count} 个过期分组",
            data={
                "cleaned_groups_count": cleaned_count,
                "ttl_hours": ttl_hours,
                "cleanup_time": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理操作失败: {str(e)}")

@router.post("/deduplication/reset", response_model=BaseResponse, summary="重置去重统计")
async def reset_deduplication_stats(
    deduplication_service: EventDeduplicationService = Depends(get_deduplication_service)
):
    """重置去重系统的统计信息"""
    try:
        deduplication_service.reset_statistics()
        
        return BaseResponse(
            success=True,
            message="去重统计信息已重置",
            data={"reset_time": datetime.utcnow().isoformat()}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置统计失败: {str(e)}")

# =============================================================================
# 服务健康状态机管理
# =============================================================================

@router.get("/state-machine/services", response_model=BaseResponse, summary="获取所有服务状态概览")
async def get_services_health_overview(
    state_manager: StateManager = Depends(get_state_manager)
):
    """获取所有服务的健康状态概览"""
    try:
        services_status = state_manager.get_services_status()
        
        return BaseResponse(
            success=True,
            message="服务状态概览获取成功",
            data=services_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务状态概览失败: {str(e)}")

@router.get("/state-machine/services/{service_name}", response_model=BaseResponse, summary="获取指定服务详细状态")
async def get_service_detailed_status(
    service_name: str,
    state_manager: StateManager = Depends(get_state_manager)
):
    """获取指定服务的详细状态信息"""
    try:
        service_details = state_manager.get_service_details(service_name)
        
        if not service_details:
            raise HTTPException(status_code=404, detail=f"服务 {service_name} 未找到")
        
        return BaseResponse(
            success=True,
            message=f"服务 {service_name} 状态获取成功",
            data=service_details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务详细状态失败: {str(e)}")

@router.get("/state-machine/episodes", response_model=BaseResponse, summary="获取所有Episode状态")
async def get_episodes_overview(
    state_manager: StateManager = Depends(get_state_manager)
):
    """获取所有Episode的状态概览"""
    try:
        episodes_status = state_manager.get_episodes_status()
        
        return BaseResponse(
            success=True,
            message="Episode状态概览获取成功",
            data=episodes_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Episode状态概览失败: {str(e)}")

@router.post("/state-machine/process-event", response_model=BaseResponse, summary="处理事件并更新状态机")
async def process_event_state_machine(
    event: UnifiedEventCreate,
    state_manager: StateManager = Depends(get_state_manager),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """处理事件并更新状态机状态"""
    try:
        # 创建统一事件对象 - 补充缺失字段
        event_data = event.dict()
        
        # 生成event_id (UUID)
        if not event_data.get("event_id"):
            import uuid
            event_data["event_id"] = str(uuid.uuid4())
        
        # 生成fingerprint
        if not event_data.get("fingerprint"):
            import hashlib
            fingerprint_data = f"{event_data['event_type']}:{event_data['service']}:{event_data['component']}:{event_data.get('message', '')}"
            event_data["fingerprint"] = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
        
        # 设置默认timestamp
        if not event_data.get("timestamp"):
            event_data["timestamp"] = datetime.utcnow()
        
        # 确保枚举类型正确
        if isinstance(event_data.get("event_type"), str):
            event_data["event_type"] = EventType(event_data["event_type"])
        if isinstance(event_data.get("severity"), str):
            event_data["severity"] = EventSeverity(event_data["severity"])  
        if isinstance(event_data.get("detection_method"), str):
            event_data["detection_method"] = DetectionMethod(event_data["detection_method"])
        if isinstance(event_data.get("component_type"), str):
            event_data["component_type"] = ComponentType(event_data["component_type"])
            
        unified_event = UnifiedEvent(**event_data)
        
        # 处理状态机事件
        state_result = await state_manager.process_event(unified_event)
        
        # 同时存储事件到数据库
        await store_event_to_falkor(unified_event, falkor_service)
        
        return BaseResponse(
            success=True,
            message="事件处理完成，状态机已更新",
            data={
                "event_id": unified_event.event_id,
                "state_machine_result": state_result
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理事件状态机失败: {str(e)}")

@router.post("/state-machine/enable", response_model=BaseResponse, summary="启用状态机")
async def enable_state_machine(
    state_manager: StateManager = Depends(get_state_manager)
):
    """启用状态管理器"""
    state_manager.enable()
    
    return BaseResponse(
        success=True,
        message="状态机已启用",
        data={"enabled": True}
    )

@router.post("/state-machine/disable", response_model=BaseResponse, summary="禁用状态机")
async def disable_state_machine(
    state_manager: StateManager = Depends(get_state_manager)
):
    """禁用状态管理器"""
    state_manager.disable()
    
    return BaseResponse(
        success=True,
        message="状态机已禁用",
        data={"enabled": False}
    )

# =============================================================================
# 事件生命周期管理
# =============================================================================

@router.patch("/{event_id}/validity", response_model=BaseResponse, summary="更新事件有效性")
async def update_event_validity(
    event_id: str,
    validity_state: TemporalValidityState,
    reason: Optional[str] = None,
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """手动更新事件的有效性状态"""
    try:
        result = await update_event_validity_state(event_id, validity_state, reason, falkor_service)
        
        return BaseResponse(
            success=True,
            message=f"事件 {event_id} 有效性已更新为 {validity_state}",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新事件有效性失败: {str(e)}")

@router.delete("/{event_id}", response_model=BaseResponse, summary="删除事件")
async def delete_event(
    event_id: str,
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """删除指定事件"""
    try:
        result = await remove_event_from_falkor(event_id, falkor_service)
        
        return BaseResponse(
            success=True,
            message=f"事件 {event_id} 已删除",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除事件失败: {str(e)}")

# =============================================================================
# 辅助函数
# =============================================================================

async def check_event_fingerprint(fingerprint: str, falkor_service: FalkorDBService) -> Optional[dict]:
    """检查事件指纹是否已存在"""
    query = f"""
    MATCH (e:Event {{fingerprint: '{fingerprint}'}})
    RETURN e
    LIMIT 1
    """
    
    try:
        result = await falkor_service.execute_query(query)
        return result[0] if result else None
    except:
        return None

async def merge_duplicate_event(existing: dict, new_event: UnifiedEvent, falkor_service: FalkorDBService) -> dict:
    """合并重复事件"""
    # 简化实现：更新现有事件的时间范围和计数
    update_query = f"""
    MATCH (e:Event {{fingerprint: '{new_event.fingerprint}'}})
    SET e.last_seen = '{new_event.timestamp.isoformat()}',
        e.occurrence_count = COALESCE(e.occurrence_count, 1) + 1
    RETURN e
    """
    
    result = await falkor_service.execute_query(update_query)
    return result[0] if result else existing

async def store_event_to_falkor(event: UnifiedEvent, falkor_service: FalkorDBService):
    """将事件存储到FalkorDB"""
    query = f"""
    CREATE (e:Event {{
        event_id: '{event.event_id}',
        event_type: '{event.event_type}',
        severity: '{event.severity}',
        confidence: {event.confidence},
        timestamp: '{event.timestamp.isoformat()}',
        source: '{event.source}',
        detection_method: '{event.detection_method}',
        fingerprint: '{event.fingerprint}',
        service: '{event.service}',
        component: '{event.component}',
        component_type: '{event.component_type}',
        namespace: '{event.namespace}',
        cluster: '{event.cluster}',
        region: '{event.region}',
        owner: '{event.owner}',
        message: '{event.message.replace("'", "\\'")}',
        ttl_sec: {event.ttl_sec or 3600},
        occurrence_count: 1,
        created_at: '{datetime.utcnow().isoformat()}'
    }})
    RETURN e
    """
    
    return await falkor_service.execute_query(query)

async def query_events_from_falkor(
    event_filter: EventFilter, 
    start_time: Optional[datetime], 
    end_time: Optional[datetime],
    falkor_service: FalkorDBService
) -> List[dict]:
    """从FalkorDB查询事件"""
    
    # 构建查询条件
    conditions = []
    
    if event_filter.event_types:
        types_str = "', '".join(event_filter.event_types)
        conditions.append(f"e.event_type IN ['{types_str}']")
        
    if event_filter.severities:
        severities_str = "', '".join(event_filter.severities)
        conditions.append(f"e.severity IN ['{severities_str}']")
        
    if event_filter.services:
        services_str = "', '".join(event_filter.services)
        conditions.append(f"e.service IN ['{services_str}']")
        
    if start_time:
        conditions.append(f"e.timestamp >= '{start_time.isoformat()}'")
        
    if end_time:
        conditions.append(f"e.timestamp <= '{end_time.isoformat()}'")
        
    if event_filter.search_query:
        conditions.append(f"e.message CONTAINS '{event_filter.search_query}'")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
    MATCH (e:Event)
    WHERE {where_clause}
    RETURN e
    ORDER BY e.timestamp DESC
    SKIP {event_filter.offset}
    LIMIT {event_filter.limit}
    """
    
    return await falkor_service.execute_query(query)

async def get_event_stats(
    start_time: Optional[datetime],
    end_time: Optional[datetime], 
    group_by: str,
    falkor_service: FalkorDBService
) -> EventAggregation:
    """获取事件统计"""
    
    # 时间条件
    time_conditions = []
    if start_time:
        time_conditions.append(f"e.timestamp >= '{start_time.isoformat()}'")
    if end_time:
        time_conditions.append(f"e.timestamp <= '{end_time.isoformat()}'")
    
    time_clause = " AND " + " AND ".join(time_conditions) if time_conditions else ""
    
    # 基础统计查询
    base_query = f"""
    MATCH (e:Event)
    WHERE 1=1 {time_clause}
    """
    
    # 总数查询
    count_query = base_query + "RETURN count(e) as total"
    total_result = await falkor_service.execute_query(count_query)
    total_count = total_result[0]['total'] if total_result else 0
    
    # 严重程度分布
    severity_query = base_query + """
    RETURN e.severity as severity, count(*) as count
    ORDER BY count DESC
    """
    severity_result = await falkor_service.execute_query(severity_query)
    severity_breakdown = {r['severity']: r['count'] for r in severity_result}
    
    # 类型分布
    type_query = base_query + """
    RETURN e.event_type as type, count(*) as count
    ORDER BY count DESC
    """
    type_result = await falkor_service.execute_query(type_query)
    type_breakdown = {r['type']: r['count'] for r in type_result}
    
    # 服务分布
    service_query = base_query + """
    RETURN e.service as service, count(*) as count
    ORDER BY count DESC
    LIMIT 10
    """
    service_result = await falkor_service.execute_query(service_query)
    service_breakdown = {r['service']: r['count'] for r in service_result}
    
    return EventAggregation(
        total_count=total_count,
        severity_breakdown=severity_breakdown,
        type_breakdown=type_breakdown,
        service_breakdown=service_breakdown,
        validity_breakdown={"valid": total_count},  # 简化实现
        time_range_covered=None  # 可以添加时间范围计算
    )

async def update_event_validity_state(
    event_id: str, 
    validity_state: TemporalValidityState, 
    reason: Optional[str],
    falkor_service: FalkorDBService
) -> dict:
    """更新事件有效性状态"""
    query = f"""
    MATCH (e:Event {{event_id: '{event_id}'}})
    SET e.validity_state = '{validity_state}',
        e.validity_updated_at = '{datetime.utcnow().isoformat()}',
        e.validity_reason = '{reason or ""}'
    RETURN e
    """
    
    result = await falkor_service.execute_query(query)
    return result[0] if result else {}

async def remove_event_from_falkor(event_id: str, falkor_service: FalkorDBService) -> dict:
    """从FalkorDB删除事件"""
    query = f"""
    MATCH (e:Event {{event_id: '{event_id}'}})
    DELETE e
    RETURN count(*) as deleted_count
    """
    
    result = await falkor_service.execute_query(query)
    return {"deleted_count": result[0]['deleted_count'] if result else 0}

# =============================================================================
# 因果分析辅助函数
# =============================================================================

async def get_events_by_ids(event_ids: List[str], falkor_service: FalkorDBService) -> List[UnifiedEvent]:
    """根据事件ID获取事件"""
    if not event_ids:
        return []
    
    ids_str = "', '".join(event_ids)
    query = f"""
    MATCH (e:Event)
    WHERE e.event_id IN ['{ids_str}']
    RETURN e
    ORDER BY e.timestamp DESC
    """
    
    results = await falkor_service.execute_query(query)
    events = []
    
    for result in results:
        event_data = result['e']
        # 简化的UnifiedEvent构造（实际应该完整映射）
        event = UnifiedEvent(
            event_id=event_data.get('event_id', ''),
            event_type=EventType(event_data.get('event_type', 'FAULT')),
            severity=EventSeverity(event_data.get('severity', 'INFO')),
            confidence=event_data.get('confidence', 1.0),
            timestamp=datetime.fromisoformat(event_data.get('timestamp', datetime.utcnow().isoformat())),
            source=event_data.get('source', ''),
            detection_method=DetectionMethod(event_data.get('detection_method', 'MANUAL')),
            fingerprint=event_data.get('fingerprint', ''),
            service=event_data.get('service', ''),
            component=event_data.get('component', ''),
            component_type=ComponentType(event_data.get('component_type', 'k8s-pod')),
            namespace=event_data.get('namespace', ''),
            cluster=event_data.get('cluster', ''),
            region=event_data.get('region', ''),
            owner=event_data.get('owner', ''),
            message=event_data.get('message', ''),
            trace_id=event_data.get('trace_id'),
            correlation_id=event_data.get('correlation_id')
        )
        events.append(event)
    
    return events

async def get_events_by_time_range(start_time: datetime, end_time: datetime, falkor_service: FalkorDBService) -> List[UnifiedEvent]:
    """根据时间范围获取事件"""
    query = f"""
    MATCH (e:Event)
    WHERE e.timestamp >= '{start_time.isoformat()}' 
      AND e.timestamp <= '{end_time.isoformat()}'
    RETURN e
    ORDER BY e.timestamp DESC
    LIMIT 100
    """
    
    results = await falkor_service.execute_query(query)
    events = []
    
    for result in results:
        event_data = result['e']
        event = UnifiedEvent(
            event_id=event_data.get('event_id', ''),
            event_type=EventType(event_data.get('event_type', 'FAULT')),
            severity=EventSeverity(event_data.get('severity', 'INFO')),
            confidence=event_data.get('confidence', 1.0),
            timestamp=datetime.fromisoformat(event_data.get('timestamp', datetime.utcnow().isoformat())),
            source=event_data.get('source', ''),
            detection_method=DetectionMethod(event_data.get('detection_method', 'MANUAL')),
            fingerprint=event_data.get('fingerprint', ''),
            service=event_data.get('service', ''),
            component=event_data.get('component', ''),
            component_type=ComponentType(event_data.get('component_type', 'k8s-pod')),
            namespace=event_data.get('namespace', ''),
            cluster=event_data.get('cluster', ''),
            region=event_data.get('region', ''),
            owner=event_data.get('owner', ''),
            message=event_data.get('message', ''),
            trace_id=event_data.get('trace_id'),
            correlation_id=event_data.get('correlation_id')
        )
        events.append(event)
    
    return events

def _calculate_confidence_distribution(relations) -> Dict[str, int]:
    """计算置信度分布"""
    distribution = {"high": 0, "medium": 0, "low": 0}
    for relation in relations:
        if relation.confidence >= 0.8:
            distribution["high"] += 1
        elif relation.confidence >= 0.6:
            distribution["medium"] += 1
        else:
            distribution["low"] += 1
    return distribution

def _calculate_causality_types(relations) -> Dict[str, int]:
    """计算因果类型分布"""
    types = {}
    for relation in relations:
        causality_type = relation.causality_type.value
        types[causality_type] = types.get(causality_type, 0) + 1
    return types

def _calculate_methods_used(relations) -> Dict[str, int]:
    """计算推理方法分布"""
    methods = {}
    for relation in relations:
        method = relation.method.value
        methods[method] = methods.get(method, 0) + 1
    return methods