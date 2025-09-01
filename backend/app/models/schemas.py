from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class NodeType(str, Enum):
    ENTITY = "entity"
    EVENT = "event"
    CONCEPT = "concept"
    EPISODE = "episode"

class RelationType(str, Enum):
    RELATED_TO = "related_to"
    CAUSES = "causes"
    CONTAINS = "contains"
    FOLLOWS = "follows"

class KnowledgeNodeCreate(BaseModel):
    name: str = Field(..., description="Node name")
    type: NodeType = Field(default=NodeType.ENTITY, description="Node type")
    content: str = Field(..., description="Node content/description")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional properties")

class KnowledgeNodeResponse(BaseModel):
    id: str
    name: str
    type: NodeType
    content: str
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None

class KnowledgeNodeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[NodeType] = None
    content: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

class RelationCreate(BaseModel):
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation_type: RelationType = Field(..., description="Relationship type")
    description: Optional[str] = Field(None, description="Relationship description")
    weight: Optional[float] = Field(default=1.0, description="Relationship weight")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional properties")

class RelationResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    description: Optional[str]
    weight: float
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None

class RelationUpdate(BaseModel):
    relation_type: Optional[RelationType] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None

class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    limit: Optional[int] = Field(default=10, description="Maximum results to return")
    timestamp: Optional[datetime] = Field(None, description="Point-in-time query")

class QueryResult(BaseModel):
    nodes: List[KnowledgeNodeResponse]
    relations: List[RelationResponse]
    confidence: float
    explanation: str

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Chat session ID")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant response")
    session_id: str = Field(..., description="Chat session ID")
    query_result: Optional[QueryResult] = Field(None, description="Knowledge graph query result")