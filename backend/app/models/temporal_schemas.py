from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone
from enum import Enum
import uuid

class TemporalEventType(str, Enum):
    """时序事件类型枚举"""
    # 基础事件类型
    INSTANTANEOUS = "instantaneous"    # 瞬时事件 (如告警触发)
    DURATIVE = "durative"             # 持续事件 (如服务中断)  
    PERIODIC = "periodic"             # 周期事件 (如定期检查)
    CONDITIONAL = "conditional"        # 条件事件 (如故障检测)
    
    # 运维专用类型
    FAULT_OCCURRENCE = "fault_occurrence"      # 故障发生
    ALERT_LIFECYCLE = "alert_lifecycle"        # 告警生命周期
    IMPACT_OBSERVATION = "impact_observation"  # 影响观测
    RESPONSE_ACTION = "response_action"        # 响应行动
    RECOVERY_PROCESS = "recovery_process"      # 恢复过程
    VALIDATION_CHECK = "validation_check"      # 验证检查
    INCIDENT_RESOLUTION = "incident_resolution" # 事故解决

class TemporalValidityState(str, Enum):
    """时序有效性状态"""
    PENDING = "pending"      # 待确认 - 事件已检测但未验证
    VALID = "valid"         # 有效 - 事件已确认且当前有效
    INVALID = "invalid"     # 无效 - 事件已失效 (条件性失效)
    EXPIRED = "expired"     # 过期 - 事件自然过期 (时间性失效)
    SUSPENDED = "suspended"  # 暂停 - 事件暂时无效
    DISPUTED = "disputed"   # 争议 - 事件有效性存疑

class StateTransition(BaseModel):
    """状态转换记录"""
    transition_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_state: TemporalValidityState = Field(..., description="源状态")
    to_state: TemporalValidityState = Field(..., description="目标状态")
    transition_time: datetime = Field(..., description="转换时间")
    trigger_event: str = Field(..., description="触发事件/条件")
    reason: str = Field(..., description="转换原因描述")
    automatic: bool = Field(default=True, description="是否自动转换")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="转换置信度")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="转换元数据")

    @validator('transition_time')
    def normalize_timezone(cls, v):
        """确保时间带有时区信息"""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

class InvalidationCondition(BaseModel):
    """失效条件定义"""
    condition_id: str = Field(..., description="条件标识")
    condition_type: str = Field(..., description="条件类型")
    condition_expression: str = Field(..., description="条件表达式")
    description: str = Field(..., description="条件描述")
    priority: int = Field(default=1, ge=1, le=10, description="条件优先级")
    auto_check: bool = Field(default=True, description="是否自动检查")
    check_interval: Optional[int] = Field(None, description="检查间隔(秒)")

class ValidationDependency(BaseModel):
    """验证依赖定义"""
    dependency_id: str = Field(..., description="依赖标识")
    dependency_type: str = Field(..., description="依赖类型")
    target_event: Optional[str] = Field(None, description="依赖的目标事件")
    condition: str = Field(..., description="依赖条件")
    description: str = Field(..., description="依赖描述")
    required: bool = Field(default=True, description="是否必需")
    timeout: Optional[int] = Field(None, description="超时时间(秒)")

class EventValidityContext(BaseModel):
    """事件有效性上下文"""
    # 基础时序信息
    occurrence_time: datetime = Field(..., description="事件发生时间")
    detection_time: Optional[datetime] = Field(None, description="事件检测时间") 
    confirmation_time: Optional[datetime] = Field(None, description="事件确认时间")
    
    # 有效性时间窗口
    validity_start: datetime = Field(..., description="有效性开始时间")
    validity_end: Optional[datetime] = Field(None, description="有效性结束时间")
    
    # 失效和依赖条件
    invalidation_conditions: List[InvalidationCondition] = Field(default_factory=list)
    validation_dependencies: List[ValidationDependency] = Field(default_factory=list)
    
    # 动态属性
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="事件可信度")
    certainty_level: str = Field(default="HIGH", description="确定性级别")
    impact_scope: Dict[str, Any] = Field(default_factory=dict, description="影响范围")
    context_tags: List[str] = Field(default_factory=list, description="上下文标签")
    
    @validator('occurrence_time', 'detection_time', 'confirmation_time', 'validity_start')
    def normalize_timezones(cls, v):
        """标准化时区"""
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    def is_valid_at(self, timestamp: datetime) -> bool:
        """检查事件在指定时间的有效性"""
        # 标准化时间戳
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # 检查基础时间窗口
        if timestamp < self.validity_start:
            return False
        if self.validity_end and timestamp > self.validity_end:
            return False
            
        return True
    
    def get_validity_state(self, current_time: Optional[datetime] = None) -> TemporalValidityState:
        """计算当前有效性状态"""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        # 检查是否还未到有效时间
        if current_time < self.validity_start:
            return TemporalValidityState.PENDING
        
        # 检查是否已过有效期
        if self.validity_end and current_time > self.validity_end:
            return TemporalValidityState.EXPIRED
        
        # 在有效期内，默认为有效 (实际应用中需要检查失效条件)
        return TemporalValidityState.VALID

class TemporalEventNode(BaseModel):
    """增强的时序事件节点"""
    # 基础标识信息
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: TemporalEventType = Field(..., description="事件类型")
    name: str = Field(..., description="事件名称")
    description: str = Field(..., description="事件描述")
    
    # 时序信息
    validity_context: EventValidityContext = Field(..., description="有效性上下文")
    current_state: TemporalValidityState = Field(default=TemporalValidityState.PENDING)
    state_history: List[StateTransition] = Field(default_factory=list, description="状态变迁历史")
    
    # 关联信息
    parent_event: Optional[str] = Field(None, description="父事件ID")
    child_events: List[str] = Field(default_factory=list, description="子事件ID列表")
    related_events: List[str] = Field(default_factory=list, description="关联事件ID列表")
    causal_chain: List[str] = Field(default_factory=list, description="因果链")
    
    # 业务属性
    severity: str = Field(default="INFO", description="严重程度")
    priority: int = Field(default=5, ge=1, le=10, description="优先级")
    category: str = Field(..., description="事件分类")
    source_system: str = Field(..., description="来源系统")
    responsible_team: Optional[str] = Field(None, description="负责团队")
    
    # 元数据
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(None)
    created_by: str = Field(default="system", description="创建者")
    tags: List[str] = Field(default_factory=list, description="标签")
    custom_properties: Dict[str, Any] = Field(default_factory=dict, description="自定义属性")
    
    def add_state_transition(self, to_state: TemporalValidityState, 
                           trigger: str, reason: str, 
                           automatic: bool = True, 
                           confidence: float = 1.0) -> StateTransition:
        """添加状态转换"""
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            transition_time=datetime.now(timezone.utc),
            trigger_event=trigger,
            reason=reason,
            automatic=automatic,
            confidence=confidence
        )
        
        self.state_history.append(transition)
        self.current_state = to_state
        self.updated_at = datetime.now(timezone.utc)
        
        return transition
    
    def is_valid_at(self, timestamp: datetime) -> bool:
        """检查事件在指定时间的有效性"""
        return self.validity_context.is_valid_at(timestamp)
    
    def get_state_at(self, timestamp: datetime) -> TemporalValidityState:
        """获取事件在指定时间的状态"""
        # 按时间倒序查找最近的状态
        for transition in reversed(self.state_history):
            if transition.transition_time <= timestamp:
                return transition.to_state
        
        # 如果没有找到转换记录，返回初始状态
        return TemporalValidityState.PENDING

class TemporalRelation(BaseModel):
    """时序关系"""
    relation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    relation_type: str = Field(..., description="关系类型")
    source_event: str = Field(..., description="源事件ID")
    target_event: str = Field(..., description="目标事件ID")
    
    # 时序约束
    temporal_constraint: Optional[Dict[str, Any]] = Field(None, description="时序约束")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="关系可信度")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="关系强度")
    
    # 有效性
    relation_validity: EventValidityContext = Field(..., description="关系有效性上下文")
    current_state: TemporalValidityState = Field(default=TemporalValidityState.VALID)
    
    # 上下文
    context: Dict[str, Any] = Field(default_factory=dict, description="关系上下文")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))