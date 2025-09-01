from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from ..models.schemas import QueryRequest, QueryResult, KnowledgeNodeResponse, RelationResponse
from ..services.graphiti_service import GraphitiService
from datetime import datetime

router = APIRouter()

def get_graphiti_service(request: Request) -> GraphitiService:
    return request.app.state.graphiti_service

@router.post("/", response_model=QueryResult)
async def query_knowledge_graph(
    query_req: QueryRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Query the knowledge graph with natural language"""
    try:
        nodes_data, relations_data = await graphiti_service.query_temporal(
            query=query_req.query,
            timestamp=query_req.timestamp,
            limit=query_req.limit
        )
        
        nodes = [
            KnowledgeNodeResponse(
                id=node['id'],
                name=node['name'],
                type=node['type'],
                content=node['content'],
                properties=node['properties'],
                created_at=node['created_at'],
                updated_at=node.get('updated_at')
            ) for node in nodes_data
        ]
        
        relations = [
            RelationResponse(
                id=rel['id'],
                source_id=rel['source_id'],
                target_id=rel['target_id'],
                relation_type=rel['relation_type'],
                description=rel.get('description'),
                weight=rel['weight'],
                properties=rel['properties'],
                created_at=rel['created_at'],
                updated_at=rel.get('updated_at')
            ) for rel in relations_data
        ]
        
        confidence = min(0.9, len(nodes) / query_req.limit) if nodes else 0.1
        explanation = f"Found {len(nodes)} nodes and {len(relations)} relations matching your query"
        
        if query_req.timestamp:
            explanation += f" at timestamp {query_req.timestamp}"
        
        return QueryResult(
            nodes=nodes,
            relations=relations,
            confidence=confidence,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_nodes(
    q: str,
    limit: Optional[int] = 10,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Simple node search endpoint"""
    try:
        nodes_data = await graphiti_service.search_nodes(q, limit=limit)
        
        nodes = [
            KnowledgeNodeResponse(
                id=node['id'],
                name=node['name'],
                type=node['type'],
                content=node['content'],
                properties=node['properties'],
                created_at=node['created_at'],
                updated_at=node.get('updated_at')
            ) for node in nodes_data
        ]
        
        return {
            "query": q,
            "results": nodes,
            "count": len(nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/temporal")
async def temporal_query(
    q: str,
    timestamp: Optional[str] = None,
    limit: Optional[int] = 10,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Temporal query endpoint"""
    try:
        parsed_timestamp = None
        if timestamp:
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid timestamp format")
        
        nodes_data, relations_data = await graphiti_service.query_temporal(
            query=q,
            timestamp=parsed_timestamp,
            limit=limit
        )
        
        return {
            "query": q,
            "timestamp": timestamp,
            "nodes": nodes_data,
            "relations": relations_data,
            "count": len(nodes_data)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))