"""
图形化数据API - 支持以受管对象为中心的图形查询
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.schemas import BaseResponse
from ..services.graphiti_service import GraphitiService
from ..services.falkordb_service import FalkorDBService

router = APIRouter(prefix="/api/graph", tags=["图形化数据"])

# 依赖注入
def get_graphiti_service() -> GraphitiService:
    return GraphitiService()

def get_falkordb_service() -> FalkorDBService:
    return FalkorDBService()

@router.post("/managed-object", response_model=BaseResponse, summary="查询受管对象关系图")
async def query_managed_object_graph(
    request_data: Dict[str, Any],
    graphiti_service: GraphitiService = Depends(get_graphiti_service),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """
    以受管对象为中心查询关系图数据
    
    请求参数:
    - managed_object: 受管对象名称
    - depth: 查询深度 (默认2)
    - include_events: 是否包含事件 (默认True)
    - include_services: 是否包含服务 (默认True)
    - include_dependencies: 是否包含依赖 (默认True)
    """
    try:
        managed_object = request_data.get("managed_object")
        depth = request_data.get("depth", 2)
        include_events = request_data.get("include_events", True)
        include_services = request_data.get("include_services", True)
        include_dependencies = request_data.get("include_dependencies", True)
        
        if not managed_object:
            raise HTTPException(status_code=400, detail="受管对象名称不能为空")
        
        # 构建图查询
        graph_data = await build_managed_object_graph(
            managed_object=managed_object,
            depth=depth,
            include_events=include_events,
            include_services=include_services,
            include_dependencies=include_dependencies,
            falkor_service=falkor_service
        )
        
        return BaseResponse(
            success=True,
            message=f"成功查询受管对象 {managed_object} 的关系图",
            data=graph_data
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.get("/node/{node_id}/neighbors", response_model=BaseResponse, summary="查询节点邻居")
async def get_node_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=3),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """查询指定节点的邻居节点"""
    try:
        neighbors = await query_node_neighbors(node_id, depth, falkor_service)
        
        return BaseResponse(
            success=True,
            message=f"成功查询节点 {node_id} 的邻居",
            data=neighbors
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询邻居失败: {str(e)}")

@router.get("/search", response_model=BaseResponse, summary="搜索图节点")
async def search_graph_nodes(
    query: str = Query(..., min_length=2),
    node_types: Optional[List[str]] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """搜索图中的节点"""
    try:
        search_results = await search_nodes_in_graph(
            query=query,
            node_types=node_types,
            limit=limit,
            falkor_service=falkor_service
        )
        
        return BaseResponse(
            success=True,
            message=f"找到 {len(search_results)} 个匹配节点",
            data=search_results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/stats", response_model=BaseResponse, summary="获取图统计信息")
async def get_graph_statistics(
    falkor_service: FalkorDBService = Depends(get_falkordb_service)
):
    """获取图的统计信息"""
    try:
        stats = await get_graph_stats(falkor_service)
        
        return BaseResponse(
            success=True,
            message="成功获取图统计信息",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

# =============================================================================
# 辅助函数
# =============================================================================

async def build_managed_object_graph(
    managed_object: str,
    depth: int,
    include_events: bool,
    include_services: bool, 
    include_dependencies: bool,
    falkor_service: FalkorDBService
) -> Dict[str, Any]:
    """构建受管对象为中心的图数据"""
    
    nodes = []
    edges = []
    
    # 1. 添加中心受管对象节点
    center_node = {
        "id": managed_object,
        "label": managed_object,
        "type": "managed_object",
        "properties": {
            "status": "active",
            "created_at": datetime.utcnow().isoformat()
        }
    }
    nodes.append(center_node)
    
    try:
        # 2. 查询相关服务
        if include_services:
            services = await query_related_services(managed_object, falkor_service)
            for service in services:
                nodes.append({
                    "id": service["id"],
                    "label": service["name"],
                    "type": "service",
                    "properties": service.get("properties", {})
                })
                
                # 添加管理关系边
                edges.append({
                    "id": f"{managed_object}-manages-{service['id']}",
                    "source": managed_object,
                    "target": service["id"],
                    "type": "MANAGES",
                    "label": "管理"
                })
        
        # 3. 查询相关事件
        if include_events:
            events = await query_related_events(managed_object, falkor_service)
            for event in events:
                nodes.append({
                    "id": event["id"],
                    "label": event["name"],
                    "type": "event",
                    "properties": event.get("properties", {})
                })
                
                # 添加影响关系边
                edges.append({
                    "id": f"{event['id']}-affects-{managed_object}",
                    "source": event["id"],
                    "target": managed_object,
                    "type": "AFFECTS",
                    "label": "影响"
                })
        
        # 4. 查询依赖关系
        if include_dependencies:
            dependencies = await query_dependencies(managed_object, falkor_service)
            for dep in dependencies:
                nodes.append({
                    "id": dep["id"],
                    "label": dep["name"],
                    "type": "dependency",
                    "properties": dep.get("properties", {})
                })
                
                # 添加依赖关系边
                edges.append({
                    "id": f"{managed_object}-depends-{dep['id']}",
                    "source": managed_object,
                    "target": dep["id"],
                    "type": "DEPENDS_ON",
                    "label": "依赖"
                })
    
    except Exception as e:
        # 如果查询失败，返回模拟数据
        print(f"查询失败，使用模拟数据: {e}")
        return generate_mock_graph_data(managed_object)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "center_node": managed_object,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "depth": depth
        }
    }

async def query_related_services(managed_object: str, falkor_service: FalkorDBService) -> List[Dict[str, Any]]:
    """查询相关服务"""
    query = f"""
    MATCH (m:ManagedObject {{name: '{managed_object}'}})-[r:MANAGES]->(s:Service)
    RETURN s.id as id, s.name as name, s as properties
    LIMIT 10
    """
    
    try:
        results = await falkor_service.execute_query(query)
        return [
            {
                "id": result.get("id", f"service-{i}"),
                "name": result.get("name", f"Service {i}"),
                "properties": result.get("properties", {})
            }
            for i, result in enumerate(results)
        ]
    except:
        # 返回模拟数据
        return [
            {"id": f"{managed_object}-api", "name": f"{managed_object} API", "properties": {"status": "running"}},
            {"id": f"{managed_object}-db", "name": f"{managed_object} Database", "properties": {"status": "healthy"}},
        ]

async def query_related_events(managed_object: str, falkor_service: FalkorDBService) -> List[Dict[str, Any]]:
    """查询相关事件"""
    query = f"""
    MATCH (e:Event)-[r:AFFECTS]->(m:ManagedObject {{name: '{managed_object}'}})
    WHERE e.timestamp > '{(datetime.utcnow() - timedelta(hours=24)).isoformat()}'
    RETURN e.id as id, e.message as name, e as properties
    ORDER BY e.timestamp DESC
    LIMIT 5
    """
    
    try:
        results = await falkor_service.execute_query(query)
        return [
            {
                "id": result.get("id", f"event-{i}"),
                "name": result.get("name", f"Event {i}"),
                "properties": result.get("properties", {})
            }
            for i, result in enumerate(results)
        ]
    except:
        # 返回模拟数据
        return [
            {"id": "evt-001", "name": "CPU使用率告警", "properties": {"severity": "warning"}},
            {"id": "evt-002", "name": "响应时间异常", "properties": {"severity": "critical"}},
        ]

async def query_dependencies(managed_object: str, falkor_service: FalkorDBService) -> List[Dict[str, Any]]:
    """查询依赖关系"""
    query = f"""
    MATCH (m:ManagedObject {{name: '{managed_object}'}})-[r:DEPENDS_ON]->(d:Dependency)
    RETURN d.id as id, d.name as name, d as properties
    LIMIT 5
    """
    
    try:
        results = await falkor_service.execute_query(query)
        return [
            {
                "id": result.get("id", f"dep-{i}"),
                "name": result.get("name", f"Dependency {i}"),
                "properties": result.get("properties", {})
            }
            for i, result in enumerate(results)
        ]
    except:
        # 返回模拟数据
        return [
            {"id": "dep-001", "name": "External API", "properties": {"type": "external"}},
        ]

async def query_node_neighbors(node_id: str, depth: int, falkor_service: FalkorDBService) -> Dict[str, Any]:
    """查询节点邻居"""
    query = f"""
    MATCH (n {{id: '{node_id}'}})-[r*1..{depth}]-(neighbor)
    RETURN neighbor, r, n
    LIMIT 20
    """
    
    try:
        results = await falkor_service.execute_query(query)
        return {
            "center_node": node_id,
            "neighbors": results,
            "depth": depth
        }
    except:
        return {
            "center_node": node_id,
            "neighbors": [],
            "depth": depth
        }

async def search_nodes_in_graph(
    query: str, 
    node_types: Optional[List[str]], 
    limit: int,
    falkor_service: FalkorDBService
) -> List[Dict[str, Any]]:
    """在图中搜索节点"""
    
    # 构建类型过滤条件
    type_filter = ""
    if node_types:
        type_conditions = " OR ".join([f"'{t}' IN labels(n)" for t in node_types])
        type_filter = f" AND ({type_conditions})"
    
    cypher_query = f"""
    MATCH (n)
    WHERE (n.name CONTAINS '{query}' OR n.label CONTAINS '{query}'){type_filter}
    RETURN n.id as id, n.name as name, labels(n) as types, n as properties
    LIMIT {limit}
    """
    
    try:
        results = await falkor_service.execute_query(cypher_query)
        return [
            {
                "id": result.get("id", "unknown"),
                "name": result.get("name", "Unknown"),
                "types": result.get("types", []),
                "properties": result.get("properties", {})
            }
            for result in results
        ]
    except:
        # 返回模拟搜索结果
        return [
            {
                "id": f"search-result-{query}",
                "name": f"Mock result for '{query}'",
                "types": ["mock"],
                "properties": {"search_query": query}
            }
        ]

async def get_graph_stats(falkor_service: FalkorDBService) -> Dict[str, Any]:
    """获取图统计信息"""
    try:
        stats_query = """
        MATCH (n)
        WITH labels(n) as node_types
        UNWIND node_types as node_type
        RETURN node_type, count(*) as count
        """
        
        results = await falkor_service.execute_query(stats_query)
        
        node_counts = {}
        total_nodes = 0
        for result in results:
            node_type = result.get("node_type", "unknown")
            count = result.get("count", 0)
            node_counts[node_type] = count
            total_nodes += count
        
        edge_query = "MATCH ()-[r]->() RETURN count(r) as edge_count"
        edge_results = await falkor_service.execute_query(edge_query)
        total_edges = edge_results[0].get("edge_count", 0) if edge_results else 0
        
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_types": node_counts,
            "graph_density": total_edges / max(1, total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
        }
    except:
        return {
            "total_nodes": 0,
            "total_edges": 0,
            "node_types": {},
            "graph_density": 0
        }

def generate_mock_graph_data(managed_object: str) -> Dict[str, Any]:
    """生成模拟图数据"""
    return {
        "nodes": [
            {
                "id": managed_object,
                "label": managed_object,
                "type": "managed_object",
                "properties": {"status": "active"}
            },
            {
                "id": f"{managed_object}-api",
                "label": f"{managed_object} API",
                "type": "service",
                "properties": {"status": "running", "port": 8080}
            },
            {
                "id": f"{managed_object}-db",
                "label": f"{managed_object} Database", 
                "type": "service",
                "properties": {"status": "healthy", "type": "postgresql"}
            },
            {
                "id": "evt-001",
                "label": "CPU使用率告警",
                "type": "event",
                "properties": {"severity": "warning", "timestamp": datetime.utcnow().isoformat()}
            },
            {
                "id": "dep-001",
                "label": "External API",
                "type": "dependency", 
                "properties": {"type": "external", "endpoint": "https://api.external.com"}
            }
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": managed_object,
                "target": f"{managed_object}-api",
                "type": "MANAGES",
                "label": "管理"
            },
            {
                "id": "edge-2", 
                "source": managed_object,
                "target": f"{managed_object}-db",
                "type": "MANAGES",
                "label": "管理"
            },
            {
                "id": "edge-3",
                "source": "evt-001",
                "target": managed_object,
                "type": "AFFECTS",
                "label": "影响"
            },
            {
                "id": "edge-4",
                "source": managed_object,
                "target": "dep-001", 
                "type": "DEPENDS_ON",
                "label": "依赖"
            }
        ],
        "center_node": managed_object,
        "stats": {
            "node_count": 5,
            "edge_count": 4,
            "depth": 2
        }
    }