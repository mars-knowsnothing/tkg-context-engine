"""
关联/因果推理引擎 (Correlation/Causality Engine)
负责分析事件间的因果关系，生成LEADS_TO、TRIGGERS、CORRELATES_WITH等关系边
支持基于拓扑、时间窗口、Trace证据和故障模式库的因果推理
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
import asyncio
import json
import math

from ..models.schemas import (
    UnifiedEvent, UnifiedEventCreate, EventType, EventSeverity,
    RelationType, RelationCreate
)

class CausalityType(str, Enum):
    """因果关系类型"""
    LEADS_TO = "LEADS_TO"           # 直接因果：A导致B
    TRIGGERS = "TRIGGERS"           # 触发关系：A触发B
    ESCALATES_TO = "ESCALATES_TO"   # 升级关系：告警→故障
    RESULTS_IN = "RESULTS_IN"       # 结果关系：操作→结果
    CORRELATES_WITH = "CORRELATES_WITH"  # 弱相关：同时发生
    SAME_AS = "SAME_AS"             # 重复事件
    PRECEDES = "PRECEDES"           # 时序先后

class CausalityMethod(str, Enum):
    """因果推理方法"""
    TOPOLOGY = "topology"           # 基于服务拓扑
    TRACE = "trace"                 # 基于分布式追踪
    TEMPORAL = "temporal"           # 基于时间窗口
    PATTERN = "pattern"             # 基于故障模式库
    STATISTICAL = "statistical"     # 基于统计相关性

@dataclass
class CausalityRule:
    """因果推理规则"""
    name: str
    description: str
    method: CausalityMethod
    causality_type: CausalityType
    
    # 事件类型条件
    cause_event_types: List[EventType]
    effect_event_types: List[EventType]
    
    # 时间约束
    time_window_seconds: int = 300  # 5分钟时间窗口
    max_time_gap_seconds: int = 60  # 最大时间间隔
    
    # 置信度计算
    base_confidence: float = 0.5
    confidence_factors: Dict[str, float] = None
    
    # 其他约束
    same_service_required: bool = False
    same_component_required: bool = False
    trace_required: bool = False
    
    enabled: bool = True

@dataclass
class ServiceTopology:
    """服务拓扑定义"""
    service_name: str
    dependencies: List[str]  # 依赖的服务
    dependents: List[str]    # 依赖此服务的服务
    component_type: str
    slo_targets: Dict[str, float] = None

@dataclass
class CausalityRelation:
    """因果关系结果"""
    cause_event_id: str
    effect_event_id: str
    causality_type: CausalityType
    confidence: float
    method: CausalityMethod
    evidence: Dict[str, Any]
    time_gap_seconds: float
    
class BaseCausalityEngine(ABC):
    """因果推理引擎基类"""
    
    def __init__(self, name: str, method: CausalityMethod):
        self.name = name
        self.method = method
        self.enabled = True
        self.rules: List[CausalityRule] = []
    
    @abstractmethod
    async def infer_causality(self, events: List[UnifiedEvent]) -> List[CausalityRelation]:
        """推理事件间的因果关系"""
        pass
    
    def add_rule(self, rule: CausalityRule):
        """添加因果推理规则"""
        self.rules.append(rule)
    
    def get_applicable_rules(self, cause_event: UnifiedEvent, effect_event: UnifiedEvent) -> List[CausalityRule]:
        """获取适用的推理规则"""
        applicable_rules = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
                
            # 检查事件类型匹配
            if (cause_event.event_type in rule.cause_event_types and 
                effect_event.event_type in rule.effect_event_types):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    def calculate_confidence(self, rule: CausalityRule, cause_event: UnifiedEvent, 
                           effect_event: UnifiedEvent, evidence: Dict[str, Any]) -> float:
        """计算因果关系置信度"""
        confidence = rule.base_confidence
        
        if rule.confidence_factors:
            # 同服务加权
            if rule.confidence_factors.get('same_service', 0) > 0:
                if cause_event.service == effect_event.service:
                    confidence += rule.confidence_factors['same_service']
            
            # Trace证据加权
            if rule.confidence_factors.get('trace_evidence', 0) > 0:
                if (cause_event.trace_id and effect_event.trace_id and 
                    cause_event.trace_id == effect_event.trace_id):
                    confidence += rule.confidence_factors['trace_evidence']
            
            # 时间接近度加权
            if rule.confidence_factors.get('time_proximity', 0) > 0:
                time_gap = abs((effect_event.timestamp - cause_event.timestamp).total_seconds())
                if time_gap <= rule.max_time_gap_seconds:
                    proximity_factor = 1.0 - (time_gap / rule.max_time_gap_seconds)
                    confidence += rule.confidence_factors['time_proximity'] * proximity_factor
        
        return min(1.0, max(0.0, confidence))

class TopologyBasedCausalityEngine(BaseCausalityEngine):
    """基于拓扑的因果推理引擎"""
    
    def __init__(self):
        super().__init__("Topology_Causality_Engine", CausalityMethod.TOPOLOGY)
        self.service_topology: Dict[str, ServiceTopology] = {}
        self._initialize_rules()
        self._initialize_topology()
    
    def _initialize_rules(self):
        """初始化拓扑因果推理规则"""
        # 上游故障导致下游错误
        upstream_fault_rule = CausalityRule(
            name="upstream_fault_leads_to_downstream_error",
            description="上游服务故障导致下游服务错误",
            method=CausalityMethod.TOPOLOGY,
            causality_type=CausalityType.LEADS_TO,
            cause_event_types=[EventType.FAULT, EventType.SLO_BREACH, EventType.SATURATION],
            effect_event_types=[EventType.ERROR_RATE_SPIKE, EventType.LATENCY_DEGRADATION],
            time_window_seconds=300,
            max_time_gap_seconds=120,
            base_confidence=0.7,
            confidence_factors={
                'topology_distance': 0.2,  # 拓扑距离越近置信度越高
                'time_proximity': 0.1
            }
        )
        
        # 数据库问题导致应用问题
        db_to_app_rule = CausalityRule(
            name="database_issue_affects_application",
            description="数据库问题影响应用服务",
            method=CausalityMethod.TOPOLOGY,
            causality_type=CausalityType.LEADS_TO,
            cause_event_types=[EventType.DB_CONN_POOL_EXHAUSTED, EventType.SATURATION],
            effect_event_types=[EventType.ERROR_RATE_SPIKE, EventType.LATENCY_DEGRADATION, EventType.CIRCUIT_BREAKER_OPEN],
            time_window_seconds=180,
            max_time_gap_seconds=60,
            base_confidence=0.8,
            confidence_factors={
                'same_service': 0.1,
                'time_proximity': 0.1
            }
        )
        
        self.add_rule(upstream_fault_rule)
        self.add_rule(db_to_app_rule)
    
    def _initialize_topology(self):
        """初始化服务拓扑"""
        # 示例拓扑配置
        topologies = [
            ServiceTopology("order-service", ["payment-service", "inventory-service"], ["api-gateway"], "application"),
            ServiceTopology("payment-service", ["redis", "payment-db"], ["order-service"], "application"),
            ServiceTopology("inventory-service", ["inventory-db"], ["order-service"], "application"),
            ServiceTopology("api-gateway", [], ["order-service", "user-service"], "gateway"),
            ServiceTopology("payment-db", [], ["payment-service"], "database"),
            ServiceTopology("inventory-db", [], ["inventory-service"], "database"),
            ServiceTopology("redis", [], ["payment-service", "session-service"], "cache")
        ]
        
        for topo in topologies:
            self.service_topology[topo.service_name] = topo
    
    async def infer_causality(self, events: List[UnifiedEvent]) -> List[CausalityRelation]:
        """基于服务拓扑推理因果关系"""
        causality_relations = []
        
        # 按时间排序事件
        sorted_events = sorted(events, key=lambda x: x.timestamp)
        
        # 两两比较事件寻找因果关系
        for i, cause_event in enumerate(sorted_events):
            for j, effect_event in enumerate(sorted_events[i+1:], i+1):
                # 检查时间窗口
                time_gap = (effect_event.timestamp - cause_event.timestamp).total_seconds()
                if time_gap > 300:  # 超过5分钟时间窗口
                    break
                    
                # 获取适用规则
                applicable_rules = self.get_applicable_rules(cause_event, effect_event)
                
                for rule in applicable_rules:
                    # 检查拓扑关系
                    if await self._check_topology_relationship(cause_event.service, effect_event.service):
                        # 计算证据
                        evidence = await self._gather_topology_evidence(cause_event, effect_event)
                        
                        # 计算置信度
                        confidence = self.calculate_confidence(rule, cause_event, effect_event, evidence)
                        
                        if confidence > 0.5:  # 置信度阈值
                            relation = CausalityRelation(
                                cause_event_id=cause_event.event_id,
                                effect_event_id=effect_event.event_id,
                                causality_type=rule.causality_type,
                                confidence=confidence,
                                method=self.method,
                                evidence=evidence,
                                time_gap_seconds=time_gap
                            )
                            causality_relations.append(relation)
        
        return causality_relations
    
    async def _check_topology_relationship(self, cause_service: str, effect_service: str) -> bool:
        """检查服务间是否存在拓扑关系"""
        if cause_service not in self.service_topology or effect_service not in self.service_topology:
            return False
        
        cause_topo = self.service_topology[cause_service]
        effect_topo = self.service_topology[effect_service]
        
        # 检查直接依赖关系
        if effect_service in cause_topo.dependents:  # cause被effect依赖
            return True
        if cause_service in effect_topo.dependencies:  # effect依赖cause
            return True
            
        # 检查间接关系（最多2跳）
        for intermediate in cause_topo.dependents:
            if intermediate in self.service_topology:
                if effect_service in self.service_topology[intermediate].dependents:
                    return True
        
        return False
    
    async def _gather_topology_evidence(self, cause_event: UnifiedEvent, effect_event: UnifiedEvent) -> Dict[str, Any]:
        """收集拓扑相关证据"""
        evidence = {
            "topology_method": True,
            "cause_service": cause_event.service,
            "effect_service": effect_event.service,
            "time_gap_seconds": (effect_event.timestamp - cause_event.timestamp).total_seconds()
        }
        
        # 添加拓扑距离信息
        if cause_event.service in self.service_topology:
            cause_topo = self.service_topology[cause_event.service]
            if effect_event.service in cause_topo.dependents:
                evidence["topology_relationship"] = "direct_dependency"
                evidence["topology_distance"] = 1
            else:
                evidence["topology_relationship"] = "indirect_dependency"  
                evidence["topology_distance"] = 2
        
        return evidence

class TraceBasedCausalityEngine(BaseCausalityEngine):
    """基于分布式追踪的因果推理引擎"""
    
    def __init__(self):
        super().__init__("Trace_Causality_Engine", CausalityMethod.TRACE)
        self._initialize_rules()
    
    def _initialize_rules(self):
        """初始化Trace因果推理规则"""
        trace_causality_rule = CausalityRule(
            name="trace_based_causality",
            description="基于相同trace_id的因果关系",
            method=CausalityMethod.TRACE,
            causality_type=CausalityType.LEADS_TO,
            cause_event_types=[EventType.FAULT, EventType.LATENCY_DEGRADATION, EventType.ERROR_RATE_SPIKE],
            effect_event_types=[EventType.ERROR_RATE_SPIKE, EventType.LATENCY_DEGRADATION, EventType.SLO_BREACH],
            time_window_seconds=60,  # Trace内事件时间窗口较短
            base_confidence=0.9,     # Trace证据置信度很高
            trace_required=True,
            confidence_factors={
                'trace_evidence': 0.1,
                'time_proximity': 0.05
            }
        )
        
        self.add_rule(trace_causality_rule)
    
    async def infer_causality(self, events: List[UnifiedEvent]) -> List[CausalityRelation]:
        """基于Trace推理因果关系"""
        causality_relations = []
        
        # 按trace_id分组事件
        trace_groups = self._group_events_by_trace(events)
        
        for trace_id, trace_events in trace_groups.items():
            if len(trace_events) < 2:
                continue
                
            # 按时间排序同一Trace内的事件
            sorted_trace_events = sorted(trace_events, key=lambda x: x.timestamp)
            
            # 分析Trace内事件的因果关系
            for i, cause_event in enumerate(sorted_trace_events):
                for j, effect_event in enumerate(sorted_trace_events[i+1:], i+1):
                    time_gap = (effect_event.timestamp - cause_event.timestamp).total_seconds()
                    
                    if time_gap > 60:  # Trace内时间窗口1分钟
                        break
                    
                    # 获取适用规则
                    applicable_rules = self.get_applicable_rules(cause_event, effect_event)
                    
                    for rule in applicable_rules:
                        evidence = {
                            "trace_method": True,
                            "shared_trace_id": trace_id,
                            "time_gap_seconds": time_gap,
                            "trace_sequence_order": j - i
                        }
                        
                        confidence = self.calculate_confidence(rule, cause_event, effect_event, evidence)
                        
                        if confidence > 0.7:  # Trace证据要求更高置信度
                            relation = CausalityRelation(
                                cause_event_id=cause_event.event_id,
                                effect_event_id=effect_event.event_id,
                                causality_type=CausalityType.LEADS_TO,
                                confidence=confidence,
                                method=CausalityMethod.TRACE,
                                evidence=evidence,
                                time_gap_seconds=time_gap
                            )
                            causality_relations.append(relation)
        
        return causality_relations
    
    def _group_events_by_trace(self, events: List[UnifiedEvent]) -> Dict[str, List[UnifiedEvent]]:
        """按trace_id分组事件"""
        trace_groups = {}
        
        for event in events:
            if event.trace_id:
                if event.trace_id not in trace_groups:
                    trace_groups[event.trace_id] = []
                trace_groups[event.trace_id].append(event)
        
        return trace_groups

class PatternBasedCausalityEngine(BaseCausalityEngine):
    """基于故障模式库的因果推理引擎"""
    
    def __init__(self):
        super().__init__("Pattern_Causality_Engine", CausalityMethod.PATTERN)
        self.fault_patterns: Dict[str, Dict[str, Any]] = {}
        self._initialize_fault_patterns()
        self._initialize_rules()
    
    def _initialize_fault_patterns(self):
        """初始化故障模式库"""
        self.fault_patterns = {
            "database_connection_exhaustion": {
                "description": "数据库连接池耗尽模式",
                "sequence": [
                    {"event_type": EventType.DB_CONN_POOL_EXHAUSTED, "order": 1},
                    {"event_type": EventType.ERROR_RATE_SPIKE, "order": 2},
                    {"event_type": EventType.CIRCUIT_BREAKER_OPEN, "order": 3}
                ],
                "max_duration_seconds": 300,
                "confidence": 0.85
            },
            "resource_saturation_cascade": {
                "description": "资源饱和级联故障",
                "sequence": [
                    {"event_type": EventType.SATURATION, "order": 1},
                    {"event_type": EventType.LATENCY_DEGRADATION, "order": 2},
                    {"event_type": EventType.SLO_BREACH, "order": 3}
                ],
                "max_duration_seconds": 180,
                "confidence": 0.8
            },
            "deployment_induced_failure": {
                "description": "部署引发的故障",
                "sequence": [
                    {"event_type": EventType.DEPLOYMENT_STARTED, "order": 1},
                    {"event_type": EventType.ERROR_RATE_SPIKE, "order": 2},
                    {"event_type": EventType.SLO_BREACH, "order": 3}
                ],
                "max_duration_seconds": 600,  # 部署后10分钟内
                "confidence": 0.9
            }
        }
    
    def _initialize_rules(self):
        """初始化模式推理规则"""
        pattern_rule = CausalityRule(
            name="fault_pattern_matching",
            description="基于故障模式库的因果推理",
            method=CausalityMethod.PATTERN,
            causality_type=CausalityType.LEADS_TO,
            cause_event_types=list(EventType),  # 支持所有事件类型
            effect_event_types=list(EventType),
            time_window_seconds=600,
            base_confidence=0.8
        )
        
        self.add_rule(pattern_rule)
    
    async def infer_causality(self, events: List[UnifiedEvent]) -> List[CausalityRelation]:
        """基于故障模式推理因果关系"""
        causality_relations = []
        
        # 按服务分组事件
        service_groups = self._group_events_by_service(events)
        
        for service, service_events in service_groups.items():
            # 对每个服务的事件进行模式匹配
            relations = await self._match_fault_patterns(service_events, service)
            causality_relations.extend(relations)
        
        return causality_relations
    
    async def _match_fault_patterns(self, events: List[UnifiedEvent], service: str) -> List[CausalityRelation]:
        """匹配故障模式"""
        relations = []
        sorted_events = sorted(events, key=lambda x: x.timestamp)
        
        for pattern_name, pattern in self.fault_patterns.items():
            # 尝试匹配模式序列
            matches = await self._find_pattern_matches(sorted_events, pattern)
            
            for match in matches:
                # 为匹配的事件序列创建因果关系
                for i in range(len(match) - 1):
                    cause_event = match[i]
                    effect_event = match[i + 1]
                    
                    time_gap = (effect_event.timestamp - cause_event.timestamp).total_seconds()
                    
                    evidence = {
                        "pattern_method": True,
                        "pattern_name": pattern_name,
                        "pattern_description": pattern["description"],
                        "sequence_position": i + 1,
                        "pattern_confidence": pattern["confidence"]
                    }
                    
                    relation = CausalityRelation(
                        cause_event_id=cause_event.event_id,
                        effect_event_id=effect_event.event_id,
                        causality_type=CausalityType.LEADS_TO,
                        confidence=pattern["confidence"],
                        method=CausalityMethod.PATTERN,
                        evidence=evidence,
                        time_gap_seconds=time_gap
                    )
                    relations.append(relation)
        
        return relations
    
    async def _find_pattern_matches(self, events: List[UnifiedEvent], pattern: Dict[str, Any]) -> List[List[UnifiedEvent]]:
        """查找模式匹配"""
        matches = []
        pattern_sequence = pattern["sequence"]
        max_duration = pattern["max_duration_seconds"]
        
        # 使用滑动窗口查找模式
        for i, start_event in enumerate(events):
            if start_event.event_type == pattern_sequence[0]["event_type"]:
                # 找到模式起始事件，尝试匹配完整序列
                match_sequence = [start_event]
                current_step = 1
                
                for j in range(i + 1, len(events)):
                    candidate_event = events[j]
                    
                    # 检查时间窗口
                    if (candidate_event.timestamp - start_event.timestamp).total_seconds() > max_duration:
                        break
                    
                    # 检查是否匹配当前步骤的事件类型
                    if (current_step < len(pattern_sequence) and 
                        candidate_event.event_type == pattern_sequence[current_step]["event_type"]):
                        match_sequence.append(candidate_event)
                        current_step += 1
                        
                        # 完整匹配
                        if current_step >= len(pattern_sequence):
                            matches.append(match_sequence.copy())
                            break
        
        return matches
    
    def _group_events_by_service(self, events: List[UnifiedEvent]) -> Dict[str, List[UnifiedEvent]]:
        """按服务分组事件"""
        service_groups = {}
        for event in events:
            if event.service not in service_groups:
                service_groups[event.service] = []
            service_groups[event.service].append(event)
        return service_groups

class CausalityOrchestrator:
    """因果关系协调器 - 统一管理所有因果推理引擎"""
    
    def __init__(self):
        self.engines: List[BaseCausalityEngine] = []
        self.enabled = True
        self.min_confidence_threshold = 0.5
        
        # 初始化推理引擎
        self._initialize_engines()
    
    def _initialize_engines(self):
        """初始化因果推理引擎"""
        self.engines = [
            TopologyBasedCausalityEngine(),
            TraceBasedCausalityEngine(), 
            PatternBasedCausalityEngine()
        ]
    
    async def infer_causality_relations(self, events: List[UnifiedEvent]) -> List[CausalityRelation]:
        """推理事件间的因果关系"""
        if not self.enabled or len(events) < 2:
            return []
        
        # 并行运行所有因果推理引擎
        causality_tasks = []
        for engine in self.engines:
            if engine.enabled:
                task = engine.infer_causality(events)
                causality_tasks.append(task)
        
        # 等待所有推理完成
        all_relations = await asyncio.gather(*causality_tasks, return_exceptions=True)
        
        # 合并和去重结果
        final_relations = []
        for result in all_relations:
            if isinstance(result, list):
                final_relations.extend(result)
            elif isinstance(result, Exception):
                print(f"因果推理引擎异常: {result}")
        
        # 过滤低置信度关系
        filtered_relations = [r for r in final_relations if r.confidence >= self.min_confidence_threshold]
        
        # 去重（相同的因果对只保留置信度最高的）
        deduplicated_relations = self._deduplicate_relations(filtered_relations)
        
        return deduplicated_relations
    
    def _deduplicate_relations(self, relations: List[CausalityRelation]) -> List[CausalityRelation]:
        """去重因果关系"""
        relation_map = {}
        
        for relation in relations:
            key = (relation.cause_event_id, relation.effect_event_id, relation.causality_type)
            
            if key not in relation_map or relation.confidence > relation_map[key].confidence:
                relation_map[key] = relation
        
        return list(relation_map.values())
    
    async def create_graph_relations(self, causality_relations: List[CausalityRelation]) -> List[RelationCreate]:
        """将因果关系转换为图关系"""
        graph_relations = []
        
        for causality in causality_relations:
            # 映射因果类型到图关系类型
            if causality.causality_type == CausalityType.LEADS_TO:
                relation_type = RelationType.CAUSES
            elif causality.causality_type == CausalityType.CORRELATES_WITH:
                relation_type = RelationType.RELATED_TO
            elif causality.causality_type == CausalityType.PRECEDES:
                relation_type = RelationType.PRECEDES
            else:
                relation_type = RelationType.RELATED_TO
            
            graph_relation = RelationCreate(
                source_id=causality.cause_event_id,
                target_id=causality.effect_event_id,
                relation_type=relation_type,
                description=f"{causality.causality_type.value} (置信度: {causality.confidence:.2f})",
                weight=causality.confidence,
                properties={
                    "causality_type": causality.causality_type.value,
                    "method": causality.method.value,
                    "confidence": causality.confidence,
                    "time_gap_seconds": causality.time_gap_seconds,
                    "evidence": causality.evidence
                }
            )
            graph_relations.append(graph_relation)
        
        return graph_relations
    
    def get_engine_status(self) -> Dict[str, Any]:
        """获取因果推理引擎状态"""
        return {
            "enabled": self.enabled,
            "min_confidence_threshold": self.min_confidence_threshold,
            "total_engines": len(self.engines),
            "active_engines": len([e for e in self.engines if e.enabled]),
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
    
    def set_confidence_threshold(self, threshold: float):
        """设置置信度阈值"""
        self.min_confidence_threshold = max(0.0, min(1.0, threshold))
    
    def enable_engine(self, engine_name: str):
        """启用指定引擎"""
        for engine in self.engines:
            if engine.name == engine_name:
                engine.enabled = True
                break
    
    def disable_engine(self, engine_name: str):
        """禁用指定引擎"""
        for engine in self.engines:
            if engine.name == engine_name:
                engine.enabled = False
                break