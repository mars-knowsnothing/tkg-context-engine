"""
推理/派生事件引擎 (Derived/Anomaly Engine)
负责从原始事件推导出高阶语义事件，如SLO_BREACH、ERROR_RATE_SPIKE、LATENCY_DEGRADATION等
支持基于规则、阈值和机器学习的推理方法
"""

from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import json
from dataclasses import dataclass

from ..models.schemas import (
    UnifiedEvent, UnifiedEventCreate, EventType, EventSeverity, 
    DetectionMethod, ComponentType, TemporalValidityState
)

class InferenceMethod(str, Enum):
    """推理方法类型"""
    RULE_BASED = "rule_based"
    THRESHOLD = "threshold"
    STATISTICAL = "statistical"
    ML_MODEL = "ml_model"
    CORRELATION = "correlation"

@dataclass
class InferenceRule:
    """推理规则定义"""
    name: str
    description: str
    method: InferenceMethod
    input_event_types: List[EventType]
    output_event_type: EventType
    conditions: Dict[str, Any]
    confidence_threshold: float = 0.7
    time_window_seconds: int = 300  # 5分钟默认时间窗口
    enabled: bool = True

@dataclass 
class EventPattern:
    """事件模式定义"""
    name: str
    events: List[Dict[str, Any]]  # 事件序列模式
    time_constraints: Dict[str, Any]  # 时间约束
    derived_event: EventType
    confidence: float

class BaseInferenceEngine(ABC):
    """推理引擎基类"""
    
    def __init__(self, name: str, method: InferenceMethod):
        self.name = name
        self.method = method
        self.enabled = True
        self.rules: List[InferenceRule] = []
        
    @abstractmethod
    async def infer_events(self, recent_events: List[UnifiedEvent]) -> List[UnifiedEventCreate]:
        """从最近事件推理出新事件"""
        pass
        
    def add_rule(self, rule: InferenceRule):
        """添加推理规则"""
        self.rules.append(rule)
        
    def remove_rule(self, rule_name: str):
        """删除推理规则"""
        self.rules = [r for r in self.rules if r.name != rule_name]
        
    def get_applicable_rules(self, events: List[UnifiedEvent]) -> List[InferenceRule]:
        """获取适用的推理规则"""
        applicable_rules = []
        event_types = set(e.event_type for e in events)
        
        for rule in self.rules:
            if rule.enabled and any(et in event_types for et in rule.input_event_types):
                applicable_rules.append(rule)
                
        return applicable_rules

class SLOBreachInferenceEngine(BaseInferenceEngine):
    """SLO违反推理引擎"""
    
    def __init__(self):
        super().__init__("SLO_Breach_Engine", InferenceMethod.THRESHOLD)
        self._initialize_rules()
    
    def _initialize_rules(self):
        """初始化SLO违反推理规则"""
        # 错误率SLO违反规则
        error_rate_rule = InferenceRule(
            name="error_rate_slo_breach",
            description="错误率超过SLO阈值推理",
            method=InferenceMethod.THRESHOLD,
            input_event_types=[EventType.ERROR_RATE_SPIKE, EventType.METRIC_THRESHOLD_BREACH],
            output_event_type=EventType.SLO_BREACH,
            conditions={
                "error_rate_threshold": 0.05,  # 5%错误率阈值
                "duration_minutes": 5,  # 持续5分钟
                "slo_type": "availability"
            },
            time_window_seconds=300
        )
        
        # 延迟SLO违反规则
        latency_rule = InferenceRule(
            name="latency_slo_breach", 
            description="延迟超过SLO阈值推理",
            method=InferenceMethod.THRESHOLD,
            input_event_types=[EventType.LATENCY_DEGRADATION, EventType.METRIC_THRESHOLD_BREACH],
            output_event_type=EventType.SLO_BREACH,
            conditions={
                "p95_latency_ms": 1000,  # P95延迟1秒阈值
                "duration_minutes": 3,   # 持续3分钟
                "slo_type": "latency"
            },
            time_window_seconds=180
        )
        
        self.add_rule(error_rate_rule)
        self.add_rule(latency_rule)
    
    async def infer_events(self, recent_events: List[UnifiedEvent]) -> List[UnifiedEventCreate]:
        """推理SLO违反事件"""
        derived_events = []
        applicable_rules = self.get_applicable_rules(recent_events)
        
        for rule in applicable_rules:
            if rule.name == "error_rate_slo_breach":
                slo_events = await self._infer_error_rate_slo_breach(recent_events, rule)
                derived_events.extend(slo_events)
            elif rule.name == "latency_slo_breach":
                slo_events = await self._infer_latency_slo_breach(recent_events, rule)
                derived_events.extend(slo_events)
                
        return derived_events
    
    async def _infer_error_rate_slo_breach(self, events: List[UnifiedEvent], rule: InferenceRule) -> List[UnifiedEventCreate]:
        """推理错误率SLO违反"""
        slo_breaches = []
        
        # 按服务分组事件
        service_events = self._group_events_by_service(events)
        
        for service, service_events_list in service_events.items():
            # 查找错误率相关事件
            error_events = [e for e in service_events_list 
                          if e.event_type in [EventType.ERROR_RATE_SPIKE, EventType.METRIC_THRESHOLD_BREACH]]
            
            if not error_events:
                continue
                
            # 分析错误率指标
            max_error_rate = 0
            for event in error_events:
                if event.metrics and 'error_rate' in event.metrics:
                    max_error_rate = max(max_error_rate, float(event.metrics['error_rate']))
            
            # 检查是否超过SLO阈值
            if max_error_rate > rule.conditions['error_rate_threshold']:
                # 创建SLO违反事件
                slo_breach = UnifiedEventCreate(
                    event_type=EventType.SLO_BREACH,
                    severity=EventSeverity.CRITICAL,
                    confidence=0.9,
                    timestamp=datetime.utcnow(),
                    source="derived_engine",
                    detection_method=DetectionMethod.THRESHOLD,
                    service=service,
                    component=error_events[0].component,
                    component_type=error_events[0].component_type,
                    namespace=error_events[0].namespace,
                    cluster=error_events[0].cluster,
                    region=error_events[0].region,
                    owner=error_events[0].owner,
                    message=f"服务 {service} 错误率 {max_error_rate:.2%} 超过SLO阈值 {rule.conditions['error_rate_threshold']:.2%}",
                    metrics={
                        "slo_type": "availability",
                        "current_error_rate": max_error_rate,
                        "slo_threshold": rule.conditions['error_rate_threshold'],
                        "breach_duration_minutes": rule.conditions['duration_minutes']
                    },
                    evidence_refs=[f"event://{e.event_id}" for e in error_events[:3]]  # 最多3个证据
                )
                slo_breaches.append(slo_breach)
        
        return slo_breaches
    
    async def _infer_latency_slo_breach(self, events: List[UnifiedEvent], rule: InferenceRule) -> List[UnifiedEventCreate]:
        """推理延迟SLO违反"""
        slo_breaches = []
        
        service_events = self._group_events_by_service(events)
        
        for service, service_events_list in service_events.items():
            latency_events = [e for e in service_events_list 
                            if e.event_type in [EventType.LATENCY_DEGRADATION, EventType.METRIC_THRESHOLD_BREACH]]
            
            if not latency_events:
                continue
                
            # 分析延迟指标
            max_p95_latency = 0
            for event in latency_events:
                if event.metrics:
                    p95_latency = event.metrics.get('p95_latency_ms', event.metrics.get('latency_ms', 0))
                    max_p95_latency = max(max_p95_latency, float(p95_latency))
            
            # 检查是否超过SLO阈值
            if max_p95_latency > rule.conditions['p95_latency_ms']:
                slo_breach = UnifiedEventCreate(
                    event_type=EventType.SLO_BREACH,
                    severity=EventSeverity.MAJOR,
                    confidence=0.85,
                    timestamp=datetime.utcnow(),
                    source="derived_engine",
                    detection_method=DetectionMethod.THRESHOLD,
                    service=service,
                    component=latency_events[0].component,
                    component_type=latency_events[0].component_type,
                    namespace=latency_events[0].namespace,
                    cluster=latency_events[0].cluster,
                    region=latency_events[0].region,
                    owner=latency_events[0].owner,
                    message=f"服务 {service} P95延迟 {max_p95_latency:.0f}ms 超过SLO阈值 {rule.conditions['p95_latency_ms']}ms",
                    metrics={
                        "slo_type": "latency",
                        "current_p95_latency_ms": max_p95_latency,
                        "slo_threshold_ms": rule.conditions['p95_latency_ms'],
                        "breach_duration_minutes": rule.conditions['duration_minutes']
                    },
                    evidence_refs=[f"event://{e.event_id}" for e in latency_events[:3]]
                )
                slo_breaches.append(slo_breach)
        
        return slo_breaches
    
    def _group_events_by_service(self, events: List[UnifiedEvent]) -> Dict[str, List[UnifiedEvent]]:
        """按服务分组事件"""
        service_events = {}
        for event in events:
            if event.service not in service_events:
                service_events[event.service] = []
            service_events[event.service].append(event)
        return service_events

class AnomalyInferenceEngine(BaseInferenceEngine):
    """异常检测推理引擎"""
    
    def __init__(self):
        super().__init__("Anomaly_Engine", InferenceMethod.STATISTICAL)
        self._initialize_rules()
    
    def _initialize_rules(self):
        """初始化异常检测规则"""
        # 错误率突增规则
        error_spike_rule = InferenceRule(
            name="error_rate_spike_detection",
            description="检测错误率异常突增",
            method=InferenceMethod.STATISTICAL,
            input_event_types=[EventType.METRIC_THRESHOLD_BREACH, EventType.LOG_PATTERN_MATCH],
            output_event_type=EventType.ERROR_RATE_SPIKE,
            conditions={
                "baseline_multiplier": 3.0,  # 超过基线3倍
                "minimum_error_rate": 0.01,  # 最低1%错误率
                "time_window_minutes": 5
            }
        )
        
        # 饱和度检测规则  
        saturation_rule = InferenceRule(
            name="saturation_detection",
            description="检测资源饱和状况",
            method=InferenceMethod.THRESHOLD,
            input_event_types=[EventType.METRIC_THRESHOLD_BREACH],
            output_event_type=EventType.SATURATION,
            conditions={
                "cpu_threshold": 0.85,      # CPU使用率85%
                "memory_threshold": 0.90,   # 内存使用率90%
                "duration_minutes": 2       # 持续2分钟
            }
        )
        
        self.add_rule(error_spike_rule)
        self.add_rule(saturation_rule)
    
    async def infer_events(self, recent_events: List[UnifiedEvent]) -> List[UnifiedEventCreate]:
        """推理异常事件"""
        derived_events = []
        applicable_rules = self.get_applicable_rules(recent_events)
        
        for rule in applicable_rules:
            if rule.name == "error_rate_spike_detection":
                spike_events = await self._detect_error_rate_spikes(recent_events, rule)
                derived_events.extend(spike_events)
            elif rule.name == "saturation_detection":
                saturation_events = await self._detect_saturation(recent_events, rule)
                derived_events.extend(saturation_events)
        
        return derived_events
    
    async def _detect_error_rate_spikes(self, events: List[UnifiedEvent], rule: InferenceRule) -> List[UnifiedEventCreate]:
        """检测错误率异常突增"""
        spike_events = []
        service_events = self._group_events_by_service(events)
        
        for service, service_events_list in service_events.items():
            # 分析错误相关事件的频率和严重程度
            error_events = [e for e in service_events_list 
                          if e.event_type in [EventType.METRIC_THRESHOLD_BREACH, EventType.LOG_PATTERN_MATCH]
                          and ('error' in e.message.lower() or e.severity in [EventSeverity.MAJOR, EventSeverity.CRITICAL])]
            
            if len(error_events) < 3:  # 至少需要3个相关事件
                continue
                
            # 简化的异常检测：短时间内大量错误事件
            time_window = timedelta(minutes=rule.conditions['time_window_minutes'])
            recent_errors = [e for e in error_events 
                           if e.timestamp >= (datetime.utcnow() - time_window)]
            
            if len(recent_errors) >= 5:  # 5分钟内5个或更多错误事件
                spike_event = UnifiedEventCreate(
                    event_type=EventType.ERROR_RATE_SPIKE,
                    severity=EventSeverity.MAJOR,
                    confidence=0.8,
                    timestamp=datetime.utcnow(),
                    source="anomaly_engine",
                    detection_method=DetectionMethod.ANOMALY,
                    service=service,
                    component=recent_errors[0].component,
                    component_type=recent_errors[0].component_type,
                    namespace=recent_errors[0].namespace,
                    cluster=recent_errors[0].cluster,
                    region=recent_errors[0].region,
                    owner=recent_errors[0].owner,
                    message=f"检测到服务 {service} 错误率异常突增：{len(recent_errors)} 个错误事件在 {rule.conditions['time_window_minutes']} 分钟内",
                    metrics={
                        "error_event_count": len(recent_errors),
                        "time_window_minutes": rule.conditions['time_window_minutes'],
                        "detection_confidence": 0.8
                    },
                    evidence_refs=[f"event://{e.event_id}" for e in recent_errors[:5]]
                )
                spike_events.append(spike_event)
        
        return spike_events
    
    async def _detect_saturation(self, events: List[UnifiedEvent], rule: InferenceRule) -> List[UnifiedEventCreate]:
        """检测资源饱和"""
        saturation_events = []
        service_events = self._group_events_by_service(events)
        
        for service, service_events_list in service_events.items():
            # 查找资源使用率相关的指标事件
            resource_events = [e for e in service_events_list 
                             if e.event_type == EventType.METRIC_THRESHOLD_BREACH
                             and e.metrics]
            
            high_cpu_events = []
            high_memory_events = []
            
            for event in resource_events:
                if 'cpu_utilization' in event.metrics:
                    cpu_util = float(event.metrics['cpu_utilization'])
                    if cpu_util > rule.conditions['cpu_threshold']:
                        high_cpu_events.append(event)
                        
                if 'memory_utilization' in event.metrics:
                    memory_util = float(event.metrics['memory_utilization'])  
                    if memory_util > rule.conditions['memory_threshold']:
                        high_memory_events.append(event)
            
            # 检测CPU饱和
            if len(high_cpu_events) >= 2:
                saturation_event = UnifiedEventCreate(
                    event_type=EventType.SATURATION,
                    severity=EventSeverity.MAJOR,
                    confidence=0.9,
                    timestamp=datetime.utcnow(),
                    source="anomaly_engine",
                    detection_method=DetectionMethod.THRESHOLD,
                    service=service,
                    component=high_cpu_events[0].component,
                    component_type=high_cpu_events[0].component_type,
                    namespace=high_cpu_events[0].namespace,
                    cluster=high_cpu_events[0].cluster,
                    region=high_cpu_events[0].region,
                    owner=high_cpu_events[0].owner,
                    message=f"检测到服务 {service} CPU饱和：使用率超过 {rule.conditions['cpu_threshold']:.0%}",
                    metrics={
                        "resource_type": "cpu",
                        "threshold": rule.conditions['cpu_threshold'],
                        "max_utilization": max(float(e.metrics['cpu_utilization']) for e in high_cpu_events),
                        "event_count": len(high_cpu_events)
                    },
                    evidence_refs=[f"event://{e.event_id}" for e in high_cpu_events[:3]]
                )
                saturation_events.append(saturation_event)
            
            # 检测内存饱和
            if len(high_memory_events) >= 2:
                saturation_event = UnifiedEventCreate(
                    event_type=EventType.SATURATION,
                    severity=EventSeverity.CRITICAL,  # 内存饱和比CPU更严重
                    confidence=0.95,
                    timestamp=datetime.utcnow(),
                    source="anomaly_engine",
                    detection_method=DetectionMethod.THRESHOLD,
                    service=service,
                    component=high_memory_events[0].component,
                    component_type=high_memory_events[0].component_type,
                    namespace=high_memory_events[0].namespace,
                    cluster=high_memory_events[0].cluster,
                    region=high_memory_events[0].region,
                    owner=high_memory_events[0].owner,
                    message=f"检测到服务 {service} 内存饱和：使用率超过 {rule.conditions['memory_threshold']:.0%}",
                    metrics={
                        "resource_type": "memory",
                        "threshold": rule.conditions['memory_threshold'],
                        "max_utilization": max(float(e.metrics['memory_utilization']) for e in high_memory_events),
                        "event_count": len(high_memory_events)
                    },
                    evidence_refs=[f"event://{e.event_id}" for e in high_memory_events[:3]]
                )
                saturation_events.append(saturation_event)
        
        return saturation_events
    
    def _group_events_by_service(self, events: List[UnifiedEvent]) -> Dict[str, List[UnifiedEvent]]:
        """按服务分组事件"""
        service_events = {}
        for event in events:
            if event.service not in service_events:
                service_events[event.service] = []
            service_events[event.service].append(event)
        return service_events

class DerivedEventOrchestrator:
    """派生事件协调器 - 统一管理所有推理引擎"""
    
    def __init__(self):
        self.engines: List[BaseInferenceEngine] = []
        self.event_history: List[UnifiedEvent] = []
        self.max_history_size = 1000  # 保持最近1000个事件
        self.enabled = True
        
        # 初始化默认推理引擎
        self._initialize_engines()
    
    def _initialize_engines(self):
        """初始化推理引擎"""
        self.engines = [
            SLOBreachInferenceEngine(),
            AnomalyInferenceEngine()
        ]
    
    async def process_events(self, new_events: List[UnifiedEvent]) -> List[UnifiedEventCreate]:
        """处理新事件并生成派生事件"""
        if not self.enabled:
            return []
        
        # 更新事件历史
        self._update_event_history(new_events)
        
        # 获取推理上下文（最近的相关事件）
        inference_context = self._get_inference_context()
        
        # 并行运行所有推理引擎
        derived_events_tasks = []
        for engine in self.engines:
            if engine.enabled:
                task = engine.infer_events(inference_context)
                derived_events_tasks.append(task)
        
        # 等待所有推理完成
        all_derived_events = await asyncio.gather(*derived_events_tasks, return_exceptions=True)
        
        # 合并结果并过滤异常
        final_derived_events = []
        for result in all_derived_events:
            if isinstance(result, list):
                final_derived_events.extend(result)
            elif isinstance(result, Exception):
                print(f"推理引擎异常: {result}")
        
        # 去重和后处理
        final_derived_events = self._deduplicate_events(final_derived_events)
        
        return final_derived_events
    
    def _update_event_history(self, new_events: List[UnifiedEvent]):
        """更新事件历史"""
        self.event_history.extend(new_events)
        
        # 保持历史大小限制
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # 按时间排序
        self.event_history.sort(key=lambda x: x.timestamp)
    
    def _get_inference_context(self, time_window_minutes: int = 30) -> List[UnifiedEvent]:
        """获取推理上下文（最近相关事件）"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        return [e for e in self.event_history if e.timestamp >= cutoff_time]
    
    def _deduplicate_events(self, events: List[UnifiedEventCreate]) -> List[UnifiedEventCreate]:
        """去重派生事件"""
        seen_fingerprints = set()
        unique_events = []
        
        for event in events:
            # 简化的指纹计算
            fingerprint = f"{event.service}_{event.event_type}_{event.component}"
            if fingerprint not in seen_fingerprints:
                seen_fingerprints.add(fingerprint)
                unique_events.append(event)
        
        return unique_events
    
    def add_engine(self, engine: BaseInferenceEngine):
        """添加推理引擎"""
        self.engines.append(engine)
    
    def remove_engine(self, engine_name: str):
        """移除推理引擎"""
        self.engines = [e for e in self.engines if e.name != engine_name]
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取推理引擎状态"""
        return {
            "enabled": self.enabled,
            "total_engines": len(self.engines),
            "active_engines": len([e for e in self.engines if e.enabled]),
            "event_history_size": len(self.event_history),
            "engines": [
                {
                    "name": engine.name,
                    "method": engine.method.value,
                    "enabled": engine.enabled,
                    "rules_count": len(engine.rules)
                } 
                for engine in self.engines
            ]
        }
    
    def enable(self):
        """启用推理协调器"""
        self.enabled = True
    
    def disable(self):
        """禁用推理协调器"""
        self.enabled = False
    
    def clear_history(self):
        """清空事件历史"""
        self.event_history = []