from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from ..models.schemas import KnowledgeNodeCreate, KnowledgeNodeResponse, KnowledgeNodeUpdate
from ..services.graphiti_service import GraphitiService
import uuid
from datetime import datetime

router = APIRouter()

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

@router.post("/", response_model=KnowledgeNodeResponse)
async def create_knowledge_node(
    node: KnowledgeNodeCreate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Create a new knowledge node"""
    try:
        node_id = await graphiti_service.create_node(
            name=node.name,
            content=node.content,
            node_type=node.type,
            properties=node.properties
        )
        
        # Create response
        response = KnowledgeNodeResponse(
            id=node_id,
            name=node.name,
            type=node.type,
            content=node.content,
            properties=node.properties or {},
            created_at=datetime.utcnow()
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[KnowledgeNodeResponse])
async def list_knowledge_nodes(
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    search: Optional[str] = None,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """List knowledge nodes with optional search and pagination"""
    try:
        if search:
            # For search, get more results to ensure we find matches
            nodes = await graphiti_service.search_nodes(search, limit=limit * 2)
        else:
            nodes = await graphiti_service.search_nodes("", limit=limit + offset)
        
        # Apply offset for pagination
        if offset > 0:
            nodes = nodes[offset:offset + limit]
        else:
            nodes = nodes[:limit]
        
        result = []
        for node in nodes:
            # Handle node type mapping and validation
            node_type = node.get('type', 'episode')
            if not node_type or node_type not in ['entity', 'event', 'concept', 'episode']:
                node_type = 'episode'  # Default to episode for GraphitiService nodes
            
            result.append(KnowledgeNodeResponse(
                id=node['id'],
                name=node['name'],
                type=node_type,
                content=node['content'],
                properties=node.get('properties', {}),
                created_at=node['created_at'] if isinstance(node['created_at'], datetime) else datetime.fromisoformat(node['created_at'].replace('Z', '+00:00')) if isinstance(node['created_at'], str) else datetime.utcnow(),
                updated_at=node.get('updated_at')
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{node_id}", response_model=KnowledgeNodeResponse)
async def get_knowledge_node(
    node_id: str,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Get a specific knowledge node"""
    try:
        node = await graphiti_service.get_node_by_id(node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return KnowledgeNodeResponse(
            id=node['id'],
            name=node['name'],
            type=_normalize_node_type(node.get('type', 'entity')),
            content=node['content'],
            properties=node.get('properties', {}),
            created_at=node['created_at'] if isinstance(node['created_at'], datetime) else datetime.fromisoformat(node['created_at'].replace('Z', '+00:00')) if isinstance(node['created_at'], str) else datetime.utcnow(),
            updated_at=node.get('updated_at')
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{node_id}", response_model=KnowledgeNodeResponse)
async def update_knowledge_node(
    node_id: str,
    update: KnowledgeNodeUpdate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Update a knowledge node"""
    try:
        # Update the node
        updated = await graphiti_service.update_node(
            node_id=node_id,
            name=update.name,
            content=update.content,
            node_type=update.type,
            properties=update.properties
        )
        
        if not updated:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Get the updated node
        node = await graphiti_service.get_node_by_id(node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="Node not found after update")
        
        return KnowledgeNodeResponse(
            id=node['id'],
            name=node['name'],
            type=_normalize_node_type(node.get('type', 'entity')),
            content=node['content'],
            properties=node.get('properties', {}),
            created_at=node['created_at'] if isinstance(node['created_at'], datetime) else datetime.fromisoformat(node['created_at'].replace('Z', '+00:00')) if isinstance(node['created_at'], str) else datetime.utcnow(),
            updated_at=node.get('updated_at')
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{node_id}")
async def delete_knowledge_node(
    node_id: str,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Delete a knowledge node"""
    try:
        deleted = await graphiti_service.delete_node(node_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return {"message": "Node deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))