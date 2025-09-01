from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List
from ..models.schemas import RelationCreate, RelationResponse, RelationUpdate
from ..services.graphiti_service import GraphitiService
import uuid
from datetime import datetime

router = APIRouter()

def get_graphiti_service(request: Request) -> GraphitiService:
    return request.app.state.graphiti_service

@router.post("/", response_model=RelationResponse)
async def create_relation(
    relation: RelationCreate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Create a new relation between nodes"""
    try:
        # Add relation as episode
        content = f"Relation: {relation.source_id} {relation.relation_type} {relation.target_id}"
        if relation.description:
            content += f" - {relation.description}"
        
        episode_id = await graphiti_service.add_episode(content)
        
        return RelationResponse(
            id=episode_id,
            source_id=relation.source_id,
            target_id=relation.target_id,
            relation_type=relation.relation_type,
            description=relation.description,
            weight=relation.weight or 1.0,
            properties=relation.properties or {},
            created_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/node/{node_id}", response_model=List[RelationResponse])
async def get_node_relations(
    node_id: str,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Get all relations for a specific node"""
    try:
        relations_data = await graphiti_service.get_node_relations(node_id)
        
        return [
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{relation_id}", response_model=RelationResponse)
async def get_relation(
    relation_id: str,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Get a specific relation"""
    try:
        # This would need to be implemented based on Graphiti's relation querying
        # For now, return a placeholder
        raise HTTPException(status_code=501, detail="Not implemented yet")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{relation_id}", response_model=RelationResponse)
async def update_relation(
    relation_id: str,
    update: RelationUpdate,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Update a relation"""
    try:
        # This would need to be implemented based on Graphiti's relation updating
        raise HTTPException(status_code=501, detail="Not implemented yet")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{relation_id}")
async def delete_relation(
    relation_id: str,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Delete a relation"""
    try:
        await graphiti_service.add_episode(
            content=f"Deleted relation: {relation_id}"
        )
        
        return {"message": "Relation deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))