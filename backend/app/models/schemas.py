from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
import hashlib
import json

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
    # Temporal relation types
    PRECEDES = "precedes"
    SUCCEEDS = "succeeds"
    OVERLAPS = "overlaps"
    DURING = "during"

class TemporalValidityState(str, Enum):
    VALID = "valid"
    INVALID = "invalid"  
    PENDING = "pending"
    EXPIRED = "expired"

# =============================================================================
# Enhanced temporal models (moved up for proper order)
# =============================================================================

class TimeInterval(BaseModel):
    """Represents a time interval with start and end times"""
    start_time: Optional[datetime] = Field(None, description="Start time of validity")
    end_time: Optional[datetime] = Field(None, description="End time of validity") 
    
    @validator('end_time')
    def validate_time_interval(cls, v, values):
        if v and values.get('start_time') and v <= values.get('start_time'):
            raise ValueError('End time must be after start time')
        return v
    
    def _normalize_datetime(self, dt: datetime) -> datetime:
        """Normalize datetime to UTC and make timezone-aware if needed"""
        from datetime import timezone
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    def is_valid_at(self, timestamp: datetime) -> bool:
        """Check if the interval is valid at a given timestamp"""
        # Normalize timestamp
        timestamp = self._normalize_datetime(timestamp)
        
        if self.start_time:
            start_time = self._normalize_datetime(self.start_time)
            if timestamp < start_time:
                return False
        if self.end_time:
            end_time = self._normalize_datetime(self.end_time)
            if timestamp > end_time:
                return False
        return True
    
    def get_validity_state(self, current_time: Optional[datetime] = None) -> TemporalValidityState:
        """Get current validity state"""
        from datetime import timezone
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Normalize current_time
        current_time = self._normalize_datetime(current_time)
            
        if self.start_time:
            start_time = self._normalize_datetime(self.start_time)
            if current_time < start_time:
                return TemporalValidityState.PENDING
        if self.end_time:
            end_time = self._normalize_datetime(self.end_time)
            if current_time > end_time:
                return TemporalValidityState.EXPIRED
        return TemporalValidityState.VALID

# =============================================================================
# 统一事件Schema规范 - 基于可观测性设计文档
# =============================================================================

class EventType(str, Enum):
    """统一事件类型枚举"""
    # 基础事件类型
    FAULT = "FAULT"
    ALERT = "ALERT" 
    K8S_EVENT = "K8S_EVENT"
    ANOMALY = "ANOMALY"
    SLO_BREACH = "SLO_BREACH"
    CHANGE = "CHANGE"
    RECOVERY = "RECOVERY"
    VALIDATION = "VALIDATION"
    INCIDENT = "INCIDENT"
    
    # 原始信号类
    LOG_PATTERN_MATCH = "LOG_PATTERN_MATCH"
    METRIC_THRESHOLD_BREACH = "METRIC_THRESHOLD_BREACH"
    TRACE_ANOMALY = "TRACE_ANOMALY"
    
    # 派生/语义类
    ERROR_RATE_SPIKE = "ERROR_RATE_SPIKE"
    LATENCY_DEGRADATION = "LATENCY_DEGRADATION"
    SATURATION = "SATURATION"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    RETRY_STORM = "RETRY_STORM"
    DB_CONN_POOL_EXHAUSTED = "DB_CONN_POOL_EXHAUSTED"
    THREAD_POOL_EXHAUSTED = "THREAD_POOL_EXHAUSTED"
    
    # 生命周期类
    ALERT_OPEN = "ALERT_OPEN"
    ALERT_ACK = "ALERT_ACK"
    ALERT_RESOLVED = "ALERT_RESOLVED"
    INCIDENT_OPEN = "INCIDENT_OPEN"
    INCIDENT_UPDATE = "INCIDENT_UPDATE"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    RECOVERY_ACTION = "RECOVERY_ACTION"
    RECOVERY_VALIDATION = "RECOVERY_VALIDATION"
    POSTMORTEM_PUBLISHED = "POSTMORTEM_PUBLISHED"
    
    # 变更/发布类
    DEPLOYMENT_STARTED = "DEPLOYMENT_STARTED"
    DEPLOYMENT_SUCCEEDED = "DEPLOYMENT_SUCCEEDED"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    FEATURE_FLAG_ON = "FEATURE_FLAG_ON"
    FEATURE_FLAG_OFF = "FEATURE_FLAG_OFF"
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"

class EventSeverity(str, Enum):
    """事件严重程度"""
    INFO = "INFO"
    WARN = "WARN"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"

class DetectionMethod(str, Enum):
    """检测方法"""
    RULE = "RULE"
    THRESHOLD = "THRESHOLD"
    ANOMALY = "ANOMALY"
    HEURISTIC = "HEURISTIC"
    ML = "ML"
    MANUAL = "MANUAL"

class ComponentType(str, Enum):
    """组件类型"""
    K8S_POD = "k8s-pod"
    DATABASE = "database"
    LOAD_BALANCER = "lb"
    REDIS = "redis"
    QUEUE = "queue"
    VM = "vm"
    FUNCTION = "function"

# =============================================================================
# 统一事件Schema - 核心数据模型
# =============================================================================

class UnifiedEvent(BaseModel):
    """统一事件Schema - 基于设计文档规范"""
    
    # 核心标识
    event_id: str = Field(..., description="事件唯一标识 (ULID/UUID)")
    event_type: EventType = Field(..., description="事件类型")
    severity: EventSeverity = Field(..., description="严重程度")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="可信度 (0.0-1.0)")
    
    # 时间信息
    timestamp: datetime = Field(..., description="事件时间戳")
    observed_start: Optional[datetime] = Field(None, description="观察开始时间")
    observed_end: Optional[datetime] = Field(None, description="观察结束时间")
    
    # 来源和检测
    source: str = Field(..., description="数据源 (prometheus|loki|k8s|lb|rds|gitops|synthetic|manual)")
    detection_method: DetectionMethod = Field(..., description="检测方法")
    fingerprint: str = Field(..., description="事件指纹 hash(template + labels)")
    
    # 关联标识
    trace_id: Optional[str] = Field(None, description="分布式追踪ID")
    correlation_id: Optional[str] = Field(None, description="关联ID (deployment_id|incident_id|run_id|trace_id)")
    
    # 服务和组件信息
    service: str = Field(..., description="服务名称 (如: svc.order)")
    component: str = Field(..., description="组件名称 (如: order-api)")
    component_type: ComponentType = Field(..., description="组件类型")
    
    # 环境和位置
    namespace: str = Field(..., description="命名空间/环境 (如: prod)")
    cluster: str = Field(..., description="集群名称 (如: cn-prod-1)")
    region: str = Field(..., description="区域 (如: cn-bj)")
    owner: str = Field(..., description="责任团队 (如: SRE-TEAM-A)")
    
    # 事件内容
    message: str = Field(..., description="事件描述/消息")
    metrics: Optional[Dict[str, Union[int, float, str]]] = Field(default_factory=dict, description="相关指标数据")
    evidence_refs: Optional[List[str]] = Field(default_factory=list, description="证据链接 ([\"log://...\",\"trace://...\",\"grafana://...\"])")
    
    # 生命周期
    ttl_sec: Optional[int] = Field(default=3600, description="生存时间 (秒)")
    
    # Pydantic模型配置
    class Config:
        use_enum_values = True
        validate_assignment = True
    
    @validator('fingerprint', pre=True, always=True)
    def generate_fingerprint(cls, v, values):
        """自动生成事件指纹"""
        if v:
            return v
        
        # 基于模板和标签生成指纹
        template_parts = [
            values.get('event_type', ''),
            values.get('service', ''),
            values.get('component', ''),
            values.get('message', '')
        ]
        template = '|'.join(str(part) for part in template_parts)
        return hashlib.md5(template.encode()).hexdigest()[:16]
    
    @validator('event_id', pre=True, always=True)
    def generate_event_id(cls, v):
        """如果没有提供event_id则自动生成"""
        if v:
            return v
        
        # 简化版ULID生成 (实际应该使用真正的ULID库)
        import uuid
        return f"evt_{uuid.uuid4().hex[:16]}"

class UnifiedEventCreate(BaseModel):
    """创建统一事件的请求模型"""
    event_type: EventType
    severity: EventSeverity = Field(default=EventSeverity.INFO)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    observed_start: Optional[datetime] = None
    observed_end: Optional[datetime] = None
    
    source: str
    detection_method: DetectionMethod = Field(default=DetectionMethod.MANUAL)
    fingerprint: Optional[str] = None
    
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    service: str
    component: str
    component_type: ComponentType
    
    namespace: str
    cluster: str
    region: str
    owner: str
    
    message: str
    metrics: Optional[Dict[str, Union[int, float, str]]] = Field(default_factory=dict)
    evidence_refs: Optional[List[str]] = Field(default_factory=list)
    
    ttl_sec: Optional[int] = Field(default=3600)

class UnifiedEventResponse(UnifiedEvent):
    """统一事件响应模型"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    # 时效状态
    validity_state: Optional[TemporalValidityState] = None
    
    # 版本信息
    version: int = Field(default=1, description="版本号")

class EventFilter(BaseModel):
    """事件过滤条件"""
    event_types: Optional[List[EventType]] = None
    severities: Optional[List[EventSeverity]] = None
    services: Optional[List[str]] = None
    components: Optional[List[str]] = None
    namespaces: Optional[List[str]] = None
    clusters: Optional[List[str]] = None
    owners: Optional[List[str]] = None
    
    # 时间范围
    time_range: Optional[TimeInterval] = None
    validity_states: Optional[List[TemporalValidityState]] = None
    
    # 文本搜索
    search_query: Optional[str] = None
    
    # 分页
    limit: int = Field(default=20, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

class EventAggregation(BaseModel):
    """事件聚合结果"""
    total_count: int
    severity_breakdown: Dict[str, int]
    type_breakdown: Dict[str, int]
    service_breakdown: Dict[str, int]
    validity_breakdown: Dict[str, int]
    time_range_covered: Optional[TimeInterval] = None

class KnowledgeNodeCreate(BaseModel):
    name: str = Field(..., description="Node name")
    type: NodeType = Field(default=NodeType.ENTITY, description="Node type")
    content: str = Field(..., description="Node content/description")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional properties")
    # Enhanced temporal fields
    valid_time: Optional[TimeInterval] = Field(None, description="Time interval when this node is/was valid")
    effective_time: Optional[datetime] = Field(None, description="When this information becomes effective")

class KnowledgeNodeResponse(BaseModel):
    id: str
    name: str
    type: NodeType
    content: str
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Enhanced temporal fields
    valid_time: Optional[TimeInterval] = None
    effective_time: Optional[datetime] = None
    validity_state: Optional[TemporalValidityState] = None
    version: Optional[int] = Field(default=1, description="Version number for history tracking")

class KnowledgeNodeUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[NodeType] = None
    content: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    valid_time: Optional[TimeInterval] = None
    effective_time: Optional[datetime] = None

class RelationCreate(BaseModel):
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation_type: RelationType = Field(..., description="Relationship type")
    description: Optional[str] = Field(None, description="Relationship description")
    weight: Optional[float] = Field(default=1.0, description="Relationship weight")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional properties")
    # Enhanced temporal fields
    valid_time: Optional[TimeInterval] = Field(None, description="Time interval when this relation is/was valid")
    effective_time: Optional[datetime] = Field(None, description="When this relation becomes effective")

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
    # Enhanced temporal fields
    valid_time: Optional[TimeInterval] = None
    effective_time: Optional[datetime] = None
    validity_state: Optional[TemporalValidityState] = None

class RelationUpdate(BaseModel):
    relation_type: Optional[RelationType] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None
    valid_time: Optional[TimeInterval] = None
    effective_time: Optional[datetime] = None

# Enhanced temporal query models
class TemporalQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    limit: Optional[int] = Field(default=10, description="Maximum results to return")
    # Temporal query parameters
    at_time: Optional[datetime] = Field(None, description="Point-in-time query")
    time_range: Optional[TimeInterval] = Field(None, description="Time range query")
    include_invalid: Optional[bool] = Field(False, description="Include invalid/expired nodes")
    validity_filter: Optional[TemporalValidityState] = Field(None, description="Filter by validity state")

class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    limit: Optional[int] = Field(default=10, description="Maximum results to return")
    timestamp: Optional[datetime] = Field(None, description="Point-in-time query")

class TemporalQueryResult(BaseModel):
    nodes: List[KnowledgeNodeResponse]
    relations: List[RelationResponse]
    confidence: float
    explanation: str
    # Temporal query metadata
    query_time: datetime = Field(default_factory=datetime.utcnow)
    temporal_scope: Optional[str] = Field(None, description="Description of temporal scope")
    validity_summary: Optional[Dict[str, int]] = Field(None, description="Count by validity state")

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

class BaseResponse(BaseModel):
    """通用API响应基类"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间戳")