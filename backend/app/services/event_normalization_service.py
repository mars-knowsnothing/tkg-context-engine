"""
事件标准化/归一层 (Event Normalizer)
负责将来自不同数据源的原始事件转换为统一事件Schema格式
支持多种数据源的接入和标准化处理
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from abc import ABC, abstractmethod
import json
import re
from enum import Enum

from ..models.schemas import (
    UnifiedEvent, UnifiedEventCreate, EventType, EventSeverity, 
    DetectionMethod, ComponentType
)

class DataSource(str, Enum):
    """支持的数据源类型"""
    PROMETHEUS = "prometheus"
    LOKI = "loki" 
    KUBERNETES = "k8s"
    JAEGER = "jaeger"
    TEMPO = "tempo"
    LOAD_BALANCER = "lb"
    RDS = "rds"
    REDIS = "redis"
    GITOPS = "gitops"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"

class BaseEventNormalizer(ABC):
    """事件标准化器基类"""
    
    def __init__(self, source: DataSource):
        self.source = source
    
    @abstractmethod
    def normalize(self, raw_event: Dict[str, Any]) -> UnifiedEventCreate:
        """将原始事件标准化为统一事件格式"""
        pass
    
    @abstractmethod
    def validate_raw_event(self, raw_event: Dict[str, Any]) -> bool:
        """验证原始事件格式是否正确"""
        pass
    
    def extract_service_info(self, raw_event: Dict[str, Any]) -> Dict[str, str]:
        """提取服务相关信息"""
        return {
            "service": raw_event.get("service", "unknown"),
            "component": raw_event.get("component", raw_event.get("service", "unknown")),
            "namespace": raw_event.get("namespace", raw_event.get("env", "default")),
            "cluster": raw_event.get("cluster", "default"),
            "region": raw_event.get("region", "default"),
            "owner": raw_event.get("owner", raw_event.get("team", "unknown"))
        }
    
    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """解析时间戳"""
        try:
            # 尝试多种时间戳格式
            formats = [
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ", 
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f"
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(timestamp_str, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
            
            # 如果都失败，尝试ISO格式解析
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return datetime.utcnow()

class PrometheusNormalizer(BaseEventNormalizer):
    """Prometheus指标数据标准化器"""
    
    def __init__(self):
        super().__init__(DataSource.PROMETHEUS)
    
    def validate_raw_event(self, raw_event: Dict[str, Any]) -> bool:
        required_fields = ["alertname", "labels", "annotations"]
        return all(field in raw_event for field in required_fields)
    
    def normalize(self, raw_event: Dict[str, Any]) -> UnifiedEventCreate:
        labels = raw_event.get("labels", {})
        annotations = raw_event.get("annotations", {})
        
        # 映射事件类型
        event_type = self._map_prometheus_event_type(raw_event.get("alertname", ""))
        
        # 映射严重程度
        severity = self._map_prometheus_severity(labels.get("severity", "info"))
        
        # 提取服务信息
        service_info = self.extract_service_info(labels)
        
        # 构建指标数据
        metrics = {}
        for key, value in labels.items():
            if key.endswith(('_rate', '_duration', '_count', '_size', '_percent')):
                try:
                    metrics[key] = float(value)
                except:
                    metrics[key] = value
        
        return UnifiedEventCreate(
            event_type=event_type,
            severity=severity,
            confidence=0.9,  # Prometheus告警通常置信度较高
            timestamp=self.parse_timestamp(raw_event.get("startsAt", "")),
            observed_start=self.parse_timestamp(raw_event.get("startsAt", "")),
            observed_end=self.parse_timestamp(raw_event.get("endsAt", "")) if raw_event.get("endsAt") else None,
            source=self.source.value,
            detection_method=DetectionMethod.THRESHOLD,
            service=service_info["service"],
            component=service_info["component"],
            component_type=self._map_component_type(labels),
            namespace=service_info["namespace"],
            cluster=service_info["cluster"], 
            region=service_info["region"],
            owner=service_info["owner"],
            message=annotations.get("summary", raw_event.get("alertname", "")),
            metrics=metrics,
            evidence_refs=[annotations.get("runbook_url", "")]
        )
    
    def _map_prometheus_event_type(self, alertname: str) -> EventType:
        """映射Prometheus告警名到事件类型"""
        alertname_lower = alertname.lower()
        
        if any(keyword in alertname_lower for keyword in ['high_error_rate', 'error_rate']):
            return EventType.ERROR_RATE_SPIKE
        elif any(keyword in alertname_lower for keyword in ['high_latency', 'latency']):
            return EventType.LATENCY_DEGRADATION
        elif any(keyword in alertname_lower for keyword in ['cpu_high', 'memory_high', 'disk_full']):
            return EventType.SATURATION
        elif any(keyword in alertname_lower for keyword in ['down', 'unavailable']):
            return EventType.FAULT
        elif any(keyword in alertname_lower for keyword in ['slo', 'sla']):
            return EventType.SLO_BREACH
        else:
            return EventType.METRIC_THRESHOLD_BREACH
    
    def _map_prometheus_severity(self, severity: str) -> EventSeverity:
        """映射Prometheus严重程度"""
        severity_map = {
            "critical": EventSeverity.CRITICAL,
            "major": EventSeverity.MAJOR,
            "warning": EventSeverity.MINOR,
            "info": EventSeverity.INFO
        }
        return severity_map.get(severity.lower(), EventSeverity.INFO)
    
    def _map_component_type(self, labels: Dict[str, str]) -> ComponentType:
        """根据标签推断组件类型"""
        if "pod" in labels or "container" in labels:
            return ComponentType.K8S_POD
        elif "database" in str(labels).lower():
            return ComponentType.DATABASE
        elif "redis" in str(labels).lower():
            return ComponentType.REDIS
        elif "queue" in str(labels).lower():
            return ComponentType.QUEUE
        else:
            return ComponentType.K8S_POD

class KubernetesNormalizer(BaseEventNormalizer):
    """Kubernetes事件标准化器"""
    
    def __init__(self):
        super().__init__(DataSource.KUBERNETES)
    
    def validate_raw_event(self, raw_event: Dict[str, Any]) -> bool:
        required_fields = ["kind", "reason", "message", "involvedObject"]
        return all(field in raw_event for field in required_fields)
    
    def normalize(self, raw_event: Dict[str, Any]) -> UnifiedEventCreate:
        involved_object = raw_event.get("involvedObject", {})
        
        # 映射K8s事件类型
        event_type = self._map_k8s_event_type(raw_event.get("reason", ""))
        
        # 映射严重程度
        severity = self._map_k8s_severity(raw_event.get("type", "Normal"))
        
        # 构建服务信息
        service_info = {
            "service": involved_object.get("name", "unknown"),
            "component": f"{involved_object.get('kind', '')}-{involved_object.get('name', '')}",
            "namespace": involved_object.get("namespace", "default"),
            "cluster": raw_event.get("cluster", "default"),
            "region": raw_event.get("region", "default"),
            "owner": raw_event.get("owner", "platform")
        }
        
        return UnifiedEventCreate(
            event_type=event_type,
            severity=severity,
            confidence=0.95,  # K8s事件通常可信度很高
            timestamp=self.parse_timestamp(raw_event.get("firstTimestamp", "")),
            observed_start=self.parse_timestamp(raw_event.get("firstTimestamp", "")),
            observed_end=self.parse_timestamp(raw_event.get("lastTimestamp", "")) if raw_event.get("lastTimestamp") else None,
            source=self.source.value,
            detection_method=DetectionMethod.RULE,
            service=service_info["service"],
            component=service_info["component"],
            component_type=self._map_k8s_component_type(involved_object.get("kind", "")),
            namespace=service_info["namespace"],
            cluster=service_info["cluster"],
            region=service_info["region"],
            owner=service_info["owner"],
            message=raw_event.get("message", ""),
            metrics={
                "count": raw_event.get("count", 1),
                "kind": involved_object.get("kind", ""),
                "reason": raw_event.get("reason", "")
            }
        )
    
    def _map_k8s_event_type(self, reason: str) -> EventType:
        """映射K8s事件原因到事件类型"""
        reason_lower = reason.lower()
        
        if reason_lower in ['crashloopbackoff', 'backoff']:
            return EventType.FAULT
        elif reason_lower in ['oomkilled', 'evicted']:
            return EventType.SATURATION
        elif reason_lower in ['failed', 'failedmount', 'failedscheduling']:
            return EventType.FAULT
        elif reason_lower in ['created', 'started', 'successfulcreate']:
            return EventType.DEPLOYMENT_STARTED
        elif reason_lower in ['killing', 'preempting']:
            return EventType.SCALE_DOWN
        else:
            return EventType.K8S_EVENT
    
    def _map_k8s_severity(self, event_type: str) -> EventSeverity:
        """映射K8s事件类型到严重程度"""
        if event_type == "Warning":
            return EventSeverity.MAJOR
        elif event_type == "Normal":
            return EventSeverity.INFO
        else:
            return EventSeverity.MINOR
    
    def _map_k8s_component_type(self, kind: str) -> ComponentType:
        """映射K8s资源类型"""
        if kind.lower() in ['pod', 'deployment', 'replicaset']:
            return ComponentType.K8S_POD
        else:
            return ComponentType.K8S_POD

class LogNormalizer(BaseEventNormalizer):
    """日志数据标准化器 (Loki等)"""
    
    def __init__(self, source: DataSource = DataSource.LOKI):
        super().__init__(source)
    
    def validate_raw_event(self, raw_event: Dict[str, Any]) -> bool:
        return "message" in raw_event or "log" in raw_event
    
    def normalize(self, raw_event: Dict[str, Any]) -> UnifiedEventCreate:
        log_message = raw_event.get("message", raw_event.get("log", ""))
        
        # 解析日志级别和内容
        event_type, severity = self._parse_log_content(log_message)
        
        # 提取服务信息
        service_info = self.extract_service_info(raw_event)
        
        return UnifiedEventCreate(
            event_type=event_type,
            severity=severity,
            confidence=0.7,  # 日志解析置信度相对较低
            timestamp=self.parse_timestamp(raw_event.get("timestamp", "")),
            source=self.source.value,
            detection_method=DetectionMethod.RULE,
            service=service_info["service"],
            component=service_info["component"],
            component_type=ComponentType.K8S_POD,
            namespace=service_info["namespace"],
            cluster=service_info["cluster"],
            region=service_info["region"],
            owner=service_info["owner"],
            message=log_message,
            metrics={
                "level": raw_event.get("level", "info"),
                "source_file": raw_event.get("source", ""),
                "line": raw_event.get("line", 0)
            }
        )
    
    def _parse_log_content(self, message: str) -> tuple[EventType, EventSeverity]:
        """解析日志内容确定事件类型和严重程度"""
        message_lower = message.lower()
        
        # 错误级别检测
        if any(keyword in message_lower for keyword in ['error', 'exception', 'fail']):
            severity = EventSeverity.MAJOR
            if any(keyword in message_lower for keyword in ['timeout', 'connection']):
                event_type = EventType.DB_CONN_POOL_EXHAUSTED
            elif 'circuit' in message_lower:
                event_type = EventType.CIRCUIT_BREAKER_OPEN
            else:
                event_type = EventType.LOG_PATTERN_MATCH
        elif any(keyword in message_lower for keyword in ['warn', 'warning']):
            severity = EventSeverity.MINOR
            event_type = EventType.LOG_PATTERN_MATCH
        else:
            severity = EventSeverity.INFO
            event_type = EventType.LOG_PATTERN_MATCH
        
        return event_type, severity

class EventNormalizationService:
    """事件标准化服务 - 统一管理所有标准化器"""
    
    def __init__(self):
        self.normalizers: Dict[DataSource, BaseEventNormalizer] = {
            DataSource.PROMETHEUS: PrometheusNormalizer(),
            DataSource.KUBERNETES: KubernetesNormalizer(),
            DataSource.LOKI: LogNormalizer(DataSource.LOKI)
        }
        
        # 服务和Owner映射配置
        self.service_owner_mapping = {
            "ittzp-auth-service": "SRE-TEAM-A",
            "order-service": "SRE-TEAM-B", 
            "payment-service": "SRE-TEAM-C"
        }
        
        # 环境配置
        self.environment_config = {
            "prod": {"cluster": "prod-cluster", "region": "cn-beijing"},
            "staging": {"cluster": "staging-cluster", "region": "cn-shanghai"}, 
            "dev": {"cluster": "dev-cluster", "region": "cn-hangzhou"}
        }
    
    def normalize_event(self, raw_event: Dict[str, Any], source: DataSource) -> Optional[UnifiedEventCreate]:
        """标准化事件"""
        try:
            if source not in self.normalizers:
                raise ValueError(f"不支持的数据源: {source}")
            
            normalizer = self.normalizers[source]
            
            if not normalizer.validate_raw_event(raw_event):
                raise ValueError(f"原始事件格式验证失败: {source}")
            
            # 执行标准化
            normalized_event = normalizer.normalize(raw_event)
            
            # 应用补齐逻辑
            normalized_event = self._enrich_event(normalized_event, raw_event)
            
            return normalized_event
            
        except Exception as e:
            print(f"事件标准化失败: {e}")
            return None
    
    def _enrich_event(self, event: UnifiedEventCreate, raw_event: Dict[str, Any]) -> UnifiedEventCreate:
        """补齐事件信息 - 根据服务名映射Owner和环境信息"""
        
        # 补齐Owner信息
        if event.service in self.service_owner_mapping:
            event.owner = self.service_owner_mapping[event.service]
        
        # 补齐环境信息
        if event.namespace in self.environment_config:
            env_config = self.environment_config[event.namespace]
            event.cluster = env_config["cluster"]
            event.region = env_config["region"]
        
        # 补齐trace_id
        if not event.trace_id and "trace_id" in raw_event:
            event.trace_id = raw_event["trace_id"]
        
        # 补齐correlation_id
        if not event.correlation_id:
            if event.trace_id:
                event.correlation_id = event.trace_id
            elif "deployment_id" in raw_event:
                event.correlation_id = raw_event["deployment_id"]
        
        return event
    
    def batch_normalize_events(self, raw_events: List[Dict[str, Any]], source: DataSource) -> List[UnifiedEventCreate]:
        """批量标准化事件"""
        normalized_events = []
        
        for raw_event in raw_events:
            normalized = self.normalize_event(raw_event, source)
            if normalized:
                normalized_events.append(normalized)
        
        return normalized_events
    
    def get_supported_sources(self) -> List[str]:
        """获取支持的数据源列表"""
        return [source.value for source in self.normalizers.keys()]
    
    def add_custom_normalizer(self, source: DataSource, normalizer: BaseEventNormalizer):
        """添加自定义标准化器"""
        self.normalizers[source] = normalizer
    
    def update_service_mapping(self, service_mappings: Dict[str, str]):
        """更新服务Owner映射"""
        self.service_owner_mapping.update(service_mappings)
    
    def update_environment_config(self, env_configs: Dict[str, Dict[str, str]]):
        """更新环境配置"""
        self.environment_config.update(env_configs)