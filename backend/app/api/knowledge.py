from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional
from ..models.schemas import KnowledgeNodeCreate, KnowledgeNodeResponse, KnowledgeNodeUpdate
from ..services.graphiti_service import GraphitiService
import uuid
from datetime import datetime

router = APIRouter()

def get_graphiti_service(request: Request) -> GraphitiService:
    return request.app.state.graphiti_service

@router.post("/", response_model=KnowledgeNodeResponse)
async def create_knowledge_node(
    node: KnowledgeNodeCreate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Create a new knowledge node"""
    try:
        # Add as episode to Graphiti
        episode_id = await graphiti_service.add_episode(
            content=f"Node: {node.name} - {node.content}"
        )
        
        # Create response
        response = KnowledgeNodeResponse(
            id=episode_id,
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
    limit: Optional[int] = 10,
    search: Optional[str] = None,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """List knowledge nodes with optional search"""
    try:
        if search:
            nodes = await graphiti_service.search_nodes(search, limit=limit)
        else:
            nodes = await graphiti_service.search_nodes("", limit=limit)
        
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
        # Search for the specific node
        nodes = await graphiti_service.search_nodes(f"id:{node_id}", limit=1)
        
        if not nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        node = nodes[0]
        
        # Handle node type mapping and validation
        node_type = node.get('type', 'episode')
        if not node_type or node_type not in ['entity', 'event', 'concept', 'episode']:
            node_type = 'episode'
        
        return KnowledgeNodeResponse(
            id=node['id'],
            name=node['name'],
            type=node_type,
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
        # Get existing node first
        nodes = await graphiti_service.search_nodes(f"id:{node_id}", limit=1)
        
        if not nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        existing_node = nodes[0]
        
        # Update fields
        updated_name = update.name if update.name is not None else existing_node['name']
        updated_content = update.content if update.content is not None else existing_node['content']
        updated_properties = update.properties if update.properties is not None else existing_node['properties']
        
        # Add updated episode
        await graphiti_service.add_episode(
            content=f"Updated Node: {updated_name} - {updated_content}"
        )
        
        return KnowledgeNodeResponse(
            id=node_id,
            name=updated_name,
            type=update.type if update.type is not None else existing_node['type'],
            content=updated_content,
            properties=updated_properties,
            created_at=existing_node['created_at'],
            updated_at=datetime.utcnow()
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
        # Check if node exists
        nodes = await graphiti_service.search_nodes(f"id:{node_id}", limit=1)
        
        if not nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Add deletion episode
        await graphiti_service.add_episode(
            content=f"Deleted node: {node_id}"
        )
        
        return {"message": "Node deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))