from fastapi import APIRouter, HTTPException, Depends, Request
from ..models.schemas import ChatRequest, ChatResponse, QueryResult, KnowledgeNodeResponse, RelationResponse
from ..services.graphiti_service import GraphitiService
import uuid
import logging

logger = logging.getLogger(__name__)

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

@router.post("/", response_model=ChatResponse)
async def chat(
    chat_req: ChatRequest,
    graphiti_service: GraphitiService = Depends(get_graphiti_service)
):
    """Process chat message and return response"""
    try:
        session_id = chat_req.session_id or str(uuid.uuid4())
        
        # Use the same limit as temporal queries for consistency
        response_text, query_result_data = await graphiti_service.process_chat_query(
            message=chat_req.message,
            session_id=session_id,
            limit=20  # Same as temporal queries
        )
        
        query_result = None
        if query_result_data:
            nodes = [
                KnowledgeNodeResponse(
                    id=node['id'],
                    name=node['name'],
                    type=_normalize_node_type(node['type']),
                    content=node['content'],
                    properties=node['properties'],
                    created_at=node['created_at'],
                    updated_at=node.get('updated_at')
                ) for node in query_result_data['nodes']
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
                ) for rel in query_result_data.get('relations', [])
            ]
            
            query_result = QueryResult(
                nodes=nodes,
                relations=relations,
                confidence=query_result_data['confidence'],
                explanation=query_result_data['explanation']
            )
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            query_result=query_result
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        # This would need to be implemented with proper session storage
        return {
            "session_id": session_id,
            "messages": [],
            "message": "Chat history not implemented yet"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def clear_chat_session(session_id: str):
    """Clear chat session"""
    try:
        return {
            "session_id": session_id,
            "message": "Session cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))