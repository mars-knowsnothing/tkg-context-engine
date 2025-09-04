"""
状态机层 (State Machine Layer) - Condition和Episode管理
负责维护服务/组件的健康状态和故障Episode，实现状态驱动的事件处理
基于设计文档中的Condition和Episode实体设计
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import asyncio
import json

from ..models.schemas import (
    UnifiedEvent, EventType, EventSeverity, 
    TemporalValidityState
)

class ServiceHealthState(str, Enum):
    """服务健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"

class EpisodeStatus(str, Enum):
    """Episode状态"""
    ACTIVE = "active"        # 正在进行中
    RESOLVED = "resolved"    # 已解决
    CLOSED = "closed"        # 已关闭
    SUPPRESSED = "suppressed" # 已抑制

@dataclass
class ServiceCondition:
    """服务状态快照 + 有效区间"""
    service_name: str
    component: str
    status: ServiceHealthState
    severity: EventSeverity
    valid_from: datetime
    valid_to: Optional[datetime] = None
    reason: str = ""
    evidence_event_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # 状态机控制
    hold_duration_seconds: int = 0  # 防抖时间
    transition_count: int = 0       # 状态转换次数
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def is_active(self, current_time: Optional[datetime] = None) -> bool:
        """检查状态是否当前有效"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        if current_time < self.valid_from:
            return False
        if self.valid_to and current_time > self.valid_to:
            return False
        return True
    
    def get_duration_seconds(self, current_time: Optional[datetime] = None) -> float:
        """获取状态持续时间"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        end_time = self.valid_to if self.valid_to else current_time
        return (end_time - self.valid_from).total_seconds()

@dataclass  
class Episode:
    """一次连续故障/降级过程"""
    episode_id: str
    service_name: str
    component: str
    start_time: datetime
    end_time: Optional[datetime] = None
    max_severity: EventSeverity = EventSeverity.INFO
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    
    # 关联事件
    trigger_event_id: str = ""  # 触发事件
    resolution_event_id: str = "" # 解决事件
    supporting_event_ids: List[str] = field(default_factory=list)
    
    # 指标和计算
    mttd_seconds: Optional[float] = None  # 故障检测时间
    mttr_seconds: Optional[float] = None  # 故障恢复时间
    impact_scope: Dict[str, Any] = field(default_factory=dict)
    
    # 外部关联
    incident_id: Optional[str] = None
    runbook_url: Optional[str] = None
    
    def get_duration_seconds(self, current_time: Optional[datetime] = None) -> float:
        """获取Episode持续时间"""
        if current_time is None:
            current_time = datetime.utcnow()
            
        end_time = self.end_time if self.end_time else current_time
        return (end_time - self.start_time).total_seconds()
    
    def add_supporting_event(self, event_id: str):
        """添加支撑事件"""
        if event_id not in self.supporting_event_ids:
            self.supporting_event_ids.append(event_id)
    
    def close(self, resolution_event_id: str, end_time: Optional[datetime] = None):
        """关闭Episode"""
        self.end_time = end_time or datetime.utcnow()
        self.resolution_event_id = resolution_event_id
        self.status = EpisodeStatus.RESOLVED
        
        # 计算MTTR
        if self.mttr_seconds is None:
            self.mttr_seconds = self.get_duration_seconds(self.end_time)

class StateTransitionRule:
    """状态转换规则"""
    
    def __init__(self, from_state: ServiceHealthState, to_state: ServiceHealthState, 
                 event_types: List[EventType], hold_duration_seconds: int = 0):
        self.from_state = from_state
        self.to_state = to_state
        self.event_types = event_types
        self.hold_duration_seconds = hold_duration_seconds
    
    def matches(self, current_state: ServiceHealthState, event: UnifiedEvent) -> bool:
        """检查是否匹配转换规则"""
        return (current_state == self.from_state and 
                event.event_type in self.event_types)

class ServiceHealthStateMachine:
    """服务健康状态机"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.current_conditions: Dict[str, ServiceCondition] = {}  # component -> condition
        self.active_episodes: Dict[str, Episode] = {}  # component -> episode
        self.closed_episodes: List[Episode] = []
        
        # 状态转换规则
        self.transition_rules = self._initialize_transition_rules()
        
        # 防抖计时器
        self.pending_transitions: Dict[str, Dict[str, Any]] = {}
    
    def _initialize_transition_rules(self) -> List[StateTransitionRule]:
        """初始化状态转换规则 - 基于设计文档"""
        return [
            # Healthy -> Degraded
            StateTransitionRule(
                ServiceHealthState.HEALTHY, ServiceHealthState.DEGRADED,
                [EventType.LATENCY_DEGRADATION, EventType.ERROR_RATE_SPIKE],
                hold_duration_seconds=60  # 持续1分钟
            ),
            
            # Healthy -> Unavailable (严重故障直接跳转)
            StateTransitionRule(
                ServiceHealthState.HEALTHY, ServiceHealthState.UNAVAILABLE,
                [EventType.SLO_BREACH, EventType.FAULT, EventType.SATURATION],
                hold_duration_seconds=0
            ),
            
            # Degraded -> Healthy (恢复)
            StateTransitionRule(
                ServiceHealthState.DEGRADED, ServiceHealthState.HEALTHY,
                [EventType.RECOVERY_VALIDATION, EventType.RECOVERY],
                hold_duration_seconds=120  # 持续2分钟确认恢复
            ),
            
            # Degraded -> Unavailable (降级变严重)
            StateTransitionRule(
                ServiceHealthState.DEGRADED, ServiceHealthState.UNAVAILABLE,
                [EventType.FAULT, EventType.SLO_BREACH],
                hold_duration_seconds=0
            ),
            
            # Unavailable -> Recovering
            StateTransitionRule(
                ServiceHealthState.UNAVAILABLE, ServiceHealthState.RECOVERING,
                [EventType.RECOVERY_ACTION],
                hold_duration_seconds=0
            ),
            
            # Recovering -> Healthy
            StateTransitionRule(
                ServiceHealthState.RECOVERING, ServiceHealthState.HEALTHY,
                [EventType.RECOVERY_VALIDATION],
                hold_duration_seconds=300  # 持续5分钟确认恢复
            ),
            
            # Recovering -> Unavailable (恢复失败)
            StateTransitionRule(
                ServiceHealthState.RECOVERING, ServiceHealthState.UNAVAILABLE,
                [EventType.FAULT, EventType.ERROR_RATE_SPIKE],
                hold_duration_seconds=0
            )
        ]
    
    async def process_event(self, event: UnifiedEvent) -> Optional[Dict[str, Any]]:
        """处理事件并可能触发状态转换"""
        component = event.component
        current_condition = self.current_conditions.get(component)
        
        # 如果没有当前状态，初始化为HEALTHY
        if not current_condition:
            current_condition = ServiceCondition(
                service_name=self.service_name,
                component=component,
                status=ServiceHealthState.HEALTHY,
                severity=EventSeverity.INFO,
                valid_from=datetime.utcnow() - timedelta(days=1)  # 默认已经健康1天
            )
            self.current_conditions[component] = current_condition
        
        # 查找匹配的转换规则
        applicable_rules = [rule for rule in self.transition_rules 
                          if rule.matches(current_condition.status, event)]
        
        if not applicable_rules:
            # 没有状态转换，但记录为支撑事件
            if component in self.active_episodes:
                self.active_episodes[component].add_supporting_event(event.event_id)
            return None
        
        # 执行状态转换
        transition_result = None
        for rule in applicable_rules:
            result = await self._execute_transition(current_condition, event, rule)
            if result:
                transition_result = result
                break
        
        return transition_result
    
    async def _execute_transition(self, condition: ServiceCondition, event: UnifiedEvent, 
                                rule: StateTransitionRule) -> Optional[Dict[str, Any]]:
        """执行状态转换"""
        component = condition.component
        
        # 检查防抖 (hold duration)
        if rule.hold_duration_seconds > 0:
            pending_key = f"{component}_{rule.to_state.value}"
            
            if pending_key not in self.pending_transitions:
                # 开始防抖计时
                self.pending_transitions[pending_key] = {
                    "rule": rule,
                    "event": event,
                    "condition": condition,
                    "start_time": datetime.utcnow()
                }
                
                # 设置定时器
                asyncio.create_task(self._handle_hold_duration(pending_key, rule.hold_duration_seconds))
                return {"status": "pending", "hold_duration_seconds": rule.hold_duration_seconds}
            else:
                # 检查是否达到防抖时间
                pending = self.pending_transitions[pending_key]
                elapsed = (datetime.utcnow() - pending["start_time"]).total_seconds()
                
                if elapsed >= rule.hold_duration_seconds:
                    # 执行状态转换
                    del self.pending_transitions[pending_key]
                    return await self._do_state_transition(condition, event, rule)
                else:
                    # 还在防抖期内
                    return {"status": "pending", "remaining_seconds": rule.hold_duration_seconds - elapsed}
        else:
            # 立即执行转换
            return await self._do_state_transition(condition, event, rule)
    
    async def _do_state_transition(self, condition: ServiceCondition, event: UnifiedEvent, 
                                 rule: StateTransitionRule) -> Dict[str, Any]:
        """实际执行状态转换"""
        old_state = condition.status
        new_state = rule.to_state
        component = condition.component
        current_time = datetime.utcnow()
        
        # 关闭当前状态
        condition.valid_to = current_time
        
        # 创建新状态
        new_condition = ServiceCondition(
            service_name=self.service_name,
            component=component,
            status=new_state,
            severity=event.severity,
            valid_from=current_time,
            reason=event.message,
            evidence_event_ids=[event.event_id],
            metrics=event.metrics or {}
        )
        
        self.current_conditions[component] = new_condition
        
        # Episode管理
        episode_actions = await self._manage_episodes(component, old_state, new_state, event)
        
        transition_result = {
            "status": "completed",
            "component": component,
            "from_state": old_state.value,
            "to_state": new_state.value,
            "trigger_event_id": event.event_id,
            "transition_time": current_time.isoformat(),
            "episode_actions": episode_actions
        }
        
        return transition_result
    
    async def _manage_episodes(self, component: str, old_state: ServiceHealthState, 
                             new_state: ServiceHealthState, event: UnifiedEvent) -> Dict[str, Any]:
        """管理Episode生命周期"""
        episode_actions = {"action": "none"}
        
        # 从健康状态转为非健康状态 -> 开始新Episode
        if (old_state == ServiceHealthState.HEALTHY and 
            new_state in [ServiceHealthState.DEGRADED, ServiceHealthState.UNAVAILABLE]):
            
            episode = Episode(
                episode_id=f"ep_{event.event_id}",
                service_name=self.service_name,
                component=component,
                start_time=event.timestamp,
                max_severity=event.severity,
                trigger_event_id=event.event_id
            )
            
            # 计算MTTD（假设事件时间戳即为检测时间）
            episode.mttd_seconds = 0  # 简化实现
            
            self.active_episodes[component] = episode
            episode_actions = {
                "action": "episode_started",
                "episode_id": episode.episode_id,
                "severity": event.severity.value
            }
        
        # 转为健康状态 -> 关闭Episode
        elif new_state == ServiceHealthState.HEALTHY and component in self.active_episodes:
            episode = self.active_episodes[component]
            episode.close(event.event_id, event.timestamp)
            
            # 移动到已关闭列表
            self.closed_episodes.append(episode)
            del self.active_episodes[component]
            
            episode_actions = {
                "action": "episode_closed", 
                "episode_id": episode.episode_id,
                "duration_seconds": episode.mttr_seconds
            }
        
        # 其他状态转换 -> 更新Episode严重程度
        elif component in self.active_episodes:
            episode = self.active_episodes[component]
            if event.severity.value > episode.max_severity.value:
                episode.max_severity = event.severity
            
            episode.add_supporting_event(event.event_id)
            episode_actions = {
                "action": "episode_updated",
                "episode_id": episode.episode_id,
                "supporting_events_count": len(episode.supporting_event_ids)
            }
        
        return episode_actions
    
    async def _handle_hold_duration(self, pending_key: str, hold_duration_seconds: int):
        """处理防抖延时"""
        await asyncio.sleep(hold_duration_seconds)
        
        # 如果防抖期间没有被取消，则执行转换
        if pending_key in self.pending_transitions:
            pending = self.pending_transitions[pending_key]
            await self._do_state_transition(pending["condition"], pending["event"], pending["rule"])
            del self.pending_transitions[pending_key]
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取服务当前状态摘要"""
        overall_state = ServiceHealthState.HEALTHY
        worst_severity = EventSeverity.INFO
        
        active_components = []
        for component, condition in self.current_conditions.items():
            if condition.is_active():
                active_components.append({
                    "component": component,
                    "status": condition.status.value,
                    "severity": condition.severity.value,
                    "duration_seconds": condition.get_duration_seconds(),
                    "reason": condition.reason
                })
                
                # 计算整体状态（取最严重的）
                if condition.status != ServiceHealthState.HEALTHY:
                    if (condition.status == ServiceHealthState.UNAVAILABLE or 
                        overall_state == ServiceHealthState.HEALTHY):
                        overall_state = condition.status
                    
                    if condition.severity.value > worst_severity.value:
                        worst_severity = condition.severity
        
        return {
            "service": self.service_name,
            "overall_state": overall_state.value,
            "worst_severity": worst_severity.value,
            "active_components": active_components,
            "active_episodes_count": len(self.active_episodes),
            "total_episodes_count": len(self.active_episodes) + len(self.closed_episodes),
            "pending_transitions": len(self.pending_transitions)
        }
    
    def get_episodes_summary(self, include_closed: bool = False) -> Dict[str, Any]:
        """获取Episode统计摘要"""
        episodes_data = {"active_episodes": []}
        
        # 活跃Episode
        for episode in self.active_episodes.values():
            episodes_data["active_episodes"].append({
                "episode_id": episode.episode_id,
                "component": episode.component,
                "status": episode.status.value,
                "duration_seconds": episode.get_duration_seconds(),
                "max_severity": episode.max_severity.value,
                "supporting_events_count": len(episode.supporting_event_ids),
                "incident_id": episode.incident_id
            })
        
        # 已关闭Episode
        if include_closed:
            episodes_data["closed_episodes"] = []
            for episode in self.closed_episodes[-10:]:  # 最近10个
                episodes_data["closed_episodes"].append({
                    "episode_id": episode.episode_id,
                    "component": episode.component,
                    "duration_seconds": episode.mttr_seconds,
                    "max_severity": episode.max_severity.value,
                    "resolution_time": episode.end_time.isoformat() if episode.end_time else None
                })
        
        return episodes_data

class StateManager:
    """状态管理器 - 统一管理所有服务的状态机"""
    
    def __init__(self):
        self.service_state_machines: Dict[str, ServiceHealthStateMachine] = {}
        self.enabled = True
        
    async def process_event(self, event: UnifiedEvent) -> Optional[Dict[str, Any]]:
        """处理事件并更新相关服务状态"""
        if not self.enabled:
            return None
        
        service = event.service
        
        # 获取或创建服务状态机
        if service not in self.service_state_machines:
            self.service_state_machines[service] = ServiceHealthStateMachine(service)
        
        state_machine = self.service_state_machines[service]
        
        # 处理事件
        result = await state_machine.process_event(event)
        
        return result
    
    def get_services_status(self) -> Dict[str, Any]:
        """获取所有服务状态概览"""
        services_status = []
        overall_health = {"healthy": 0, "degraded": 0, "unavailable": 0, "recovering": 0}
        
        for service_name, state_machine in self.service_state_machines.items():
            status = state_machine.get_current_status()
            services_status.append(status)
            
            # 统计整体健康度
            state = status["overall_state"]
            if state in overall_health:
                overall_health[state] += 1
        
        return {
            "total_services": len(self.service_state_machines),
            "overall_health_distribution": overall_health,
            "services": services_status
        }
    
    def get_episodes_status(self) -> Dict[str, Any]:
        """获取所有Episode状态"""
        total_active = 0
        total_closed = 0
        severity_distribution = {"INFO": 0, "MINOR": 0, "MAJOR": 0, "CRITICAL": 0}
        
        for state_machine in self.service_state_machines.values():
            total_active += len(state_machine.active_episodes)
            total_closed += len(state_machine.closed_episodes)
            
            # 统计严重程度分布
            for episode in state_machine.active_episodes.values():
                severity = episode.max_severity.value
                if severity in severity_distribution:
                    severity_distribution[severity] += 1
        
        return {
            "active_episodes": total_active,
            "closed_episodes": total_closed,
            "severity_distribution": severity_distribution
        }
    
    def get_service_details(self, service_name: str) -> Optional[Dict[str, Any]]:
        """获取指定服务详细状态"""
        if service_name not in self.service_state_machines:
            return None
        
        state_machine = self.service_state_machines[service_name]
        status = state_machine.get_current_status()
        episodes = state_machine.get_episodes_summary(include_closed=True)
        
        return {
            "service_status": status,
            "episodes": episodes
        }
    
    def enable(self):
        """启用状态管理"""
        self.enabled = True
    
    def disable(self):
        """禁用状态管理"""
        self.enabled = False