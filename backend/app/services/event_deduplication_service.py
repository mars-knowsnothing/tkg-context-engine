"""
事件指纹与去重服务

实现基于多维度指纹的事件去重机制，支持：
1. 智能指纹生成（基于关键字段组合）
2. 时间窗口去重策略
3. 相似事件聚合
4. 频率阈值过滤
5. 动态去重策略调整
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from ..models.schemas import (
    UnifiedEvent, EventType, EventSeverity, 
    DetectionMethod, ComponentType
)


class DeduplicationStrategy(Enum):
    """去重策略枚举"""
    EXACT_MATCH = "exact_match"          # 完全匹配
    FUZZY_MATCH = "fuzzy_match"          # 模糊匹配
    TIME_WINDOW = "time_window"          # 时间窗口
    FREQUENCY_THRESHOLD = "frequency_threshold"  # 频率阈值
    SIMILARITY_BASED = "similarity_based"        # 相似度匹配


@dataclass
class FingerprintConfig:
    """指纹配置"""
    # 核心字段权重配置
    service_weight: float = 0.3
    component_weight: float = 0.25
    event_type_weight: float = 0.25
    message_weight: float = 0.15
    namespace_weight: float = 0.05
    
    # 时间窗口配置
    time_window_minutes: int = 5
    
    # 频率阈值配置
    frequency_threshold: int = 10  # 5分钟内超过10次则聚合
    
    # 相似度阈值
    similarity_threshold: float = 0.85
    
    # 消息相似度配置
    ignore_numbers: bool = True  # 忽略数字差异
    ignore_timestamps: bool = True  # 忽略时间戳
    ignore_ids: bool = True  # 忽略ID类字符串


@dataclass
class EventGroup:
    """事件分组"""
    fingerprint: str
    canonical_event: UnifiedEvent  # 代表事件
    events: List[UnifiedEvent] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    occurrence_count: int = 0
    aggregated_data: Dict[str, Any] = field(default_factory=dict)


class EventDeduplicationService:
    """事件去重服务"""
    
    def __init__(self, config: FingerprintConfig = None):
        self.config = config or FingerprintConfig()
        self.event_groups: Dict[str, EventGroup] = {}
        self.fingerprint_cache: Dict[str, str] = {}
        
        # 统计信息
        self.stats = {
            "total_events_processed": 0,
            "total_duplicates_found": 0,
            "total_groups_created": 0,
            "avg_group_size": 0.0
        }
        
    def generate_fingerprint(self, event: UnifiedEvent, strategy: DeduplicationStrategy = DeduplicationStrategy.FUZZY_MATCH) -> str:
        """
        生成事件指纹
        
        Args:
            event: 统一事件对象
            strategy: 去重策略
            
        Returns:
            生成的指纹字符串
        """
        if strategy == DeduplicationStrategy.EXACT_MATCH:
            return self._generate_exact_fingerprint(event)
        elif strategy == DeduplicationStrategy.FUZZY_MATCH:
            return self._generate_fuzzy_fingerprint(event)
        elif strategy == DeduplicationStrategy.TIME_WINDOW:
            return self._generate_time_window_fingerprint(event)
        elif strategy == DeduplicationStrategy.SIMILARITY_BASED:
            return self._generate_similarity_fingerprint(event)
        else:
            return self._generate_fuzzy_fingerprint(event)  # 默认策略
    
    def _generate_exact_fingerprint(self, event: UnifiedEvent) -> str:
        """生成精确匹配指纹"""
        # 包含所有关键字段的完整指纹
        # 安全地获取枚举值
        event_type_val = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        component_type_val = event.component_type.value if hasattr(event.component_type, 'value') else str(event.component_type)
        severity_val = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        
        fingerprint_parts = [
            event_type_val,
            event.service,
            event.component,
            component_type_val,
            event.namespace,
            event.cluster,
            event.message,
            severity_val
        ]
        
        fingerprint_data = "|".join(str(part) for part in fingerprint_parts)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
    
    def _generate_fuzzy_fingerprint(self, event: UnifiedEvent) -> str:
        """生成模糊匹配指纹（忽略时间戳、数字等动态内容）"""
        # 标准化消息内容
        normalized_message = self._normalize_message(event.message)
        
        # 安全地获取枚举值
        event_type_val = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        component_type_val = event.component_type.value if hasattr(event.component_type, 'value') else str(event.component_type)
        severity_val = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        
        fingerprint_parts = [
            event_type_val,
            event.service,
            event.component,
            component_type_val,
            event.namespace,
            normalized_message,
            severity_val
        ]
        
        fingerprint_data = "|".join(str(part) for part in fingerprint_parts)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
    
    def _generate_time_window_fingerprint(self, event: UnifiedEvent) -> str:
        """生成时间窗口指纹（将时间舍入到窗口边界）"""
        # 计算时间窗口
        window_minutes = self.config.time_window_minutes
        timestamp_minutes = event.timestamp.minute // window_minutes * window_minutes
        window_timestamp = event.timestamp.replace(minute=timestamp_minutes, second=0, microsecond=0)
        
        # 安全地获取枚举值
        event_type_val = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        
        fingerprint_parts = [
            event_type_val,
            event.service,
            event.component,
            window_timestamp.isoformat(),
            self._normalize_message(event.message)
        ]
        
        fingerprint_data = "|".join(str(part) for part in fingerprint_parts)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
    
    def _generate_similarity_fingerprint(self, event: UnifiedEvent) -> str:
        """生成相似度匹配指纹（用于后续相似度计算）"""
        # 提取关键特征向量
        # 安全地获取枚举值
        event_type_val = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        severity_val = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        
        features = {
            "service": event.service,
            "component": event.component,
            "event_type": event_type_val,
            "severity": severity_val,
            "message_tokens": self._tokenize_message(event.message),
            "namespace": event.namespace
        }
        
        # 生成特征指纹
        feature_str = json.dumps(features, sort_keys=True)
        return hashlib.sha256(feature_str.encode()).hexdigest()[:16]
    
    def _normalize_message(self, message: str) -> str:
        """标准化消息内容，移除动态部分"""
        import re
        
        normalized = message.lower()
        
        if self.config.ignore_numbers:
            # 替换数字为占位符
            normalized = re.sub(r'\d+', '<NUM>', normalized)
        
        if self.config.ignore_timestamps:
            # 替换时间戳模式
            timestamp_patterns = [
                r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',  # ISO timestamp
                r'\d{2}:\d{2}:\d{2}',  # Time only
                r'\d{4}/\d{2}/\d{2}',  # Date slash format
            ]
            for pattern in timestamp_patterns:
                normalized = re.sub(pattern, '<TIMESTAMP>', normalized)
        
        if self.config.ignore_ids:
            # 替换ID模式
            id_patterns = [
                r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',  # UUID
                r'[a-f0-9]{32}',  # MD5
                r'[a-f0-9]{40}',  # SHA1
                r'id[:\s=]+[a-zA-Z0-9]+',  # ID fields
            ]
            for pattern in id_patterns:
                normalized = re.sub(pattern, '<ID>', normalized, flags=re.IGNORECASE)
        
        # 移除多余空格
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _tokenize_message(self, message: str) -> List[str]:
        """将消息分词用于相似度计算"""
        import re
        
        # 简单分词：按空格和标点分割
        tokens = re.findall(r'\w+', message.lower())
        
        # 移除停用词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        filtered_tokens = [token for token in tokens if token not in stop_words and len(token) > 2]
        
        return filtered_tokens
    
    def deduplicate_event(self, event: UnifiedEvent, strategy: DeduplicationStrategy = DeduplicationStrategy.FUZZY_MATCH) -> Tuple[bool, Optional[EventGroup]]:
        """
        对事件进行去重处理
        
        Args:
            event: 待处理的事件
            strategy: 去重策略
            
        Returns:
            Tuple[是否为重复事件, 事件分组]
        """
        self.stats["total_events_processed"] += 1
        
        # 生成指纹
        fingerprint = self.generate_fingerprint(event, strategy)
        
        # 检查是否已存在相同指纹的分组
        if fingerprint in self.event_groups:
            # 找到重复事件
            group = self.event_groups[fingerprint]
            self._update_event_group(group, event)
            self.stats["total_duplicates_found"] += 1
            return True, group
        else:
            # 创建新的事件分组
            group = EventGroup(
                fingerprint=fingerprint,
                canonical_event=event,
                events=[event],
                first_seen=event.timestamp,
                last_seen=event.timestamp,
                occurrence_count=1
            )
            self.event_groups[fingerprint] = group
            self.stats["total_groups_created"] += 1
            return False, group
    
    def _update_event_group(self, group: EventGroup, event: UnifiedEvent):
        """更新事件分组"""
        group.events.append(event)
        group.last_seen = event.timestamp
        group.occurrence_count += 1
        
        # 更新聚合数据
        self._update_aggregated_data(group, event)
        
        # 如果新事件严重程度更高，更新代表事件
        if self._get_severity_level(event.severity) > self._get_severity_level(group.canonical_event.severity):
            group.canonical_event = event
    
    def _update_aggregated_data(self, group: EventGroup, event: UnifiedEvent):
        """更新聚合统计数据"""
        if not group.aggregated_data:
            group.aggregated_data = {
                "severity_counts": {},
                "source_counts": {},
                "detection_method_counts": {},
                "time_distribution": {},
                "affected_components": set(),
                "related_traces": set(),
                "total_confidence": 0.0,
                "avg_confidence": 0.0
            }
        
        agg = group.aggregated_data
        
        # 严重程度统计
        severity = event.severity.value
        agg["severity_counts"][severity] = agg["severity_counts"].get(severity, 0) + 1
        
        # 数据源统计
        source = event.source
        agg["source_counts"][source] = agg["source_counts"].get(source, 0) + 1
        
        # 检测方法统计
        method = event.detection_method.value
        agg["detection_method_counts"][method] = agg["detection_method_counts"].get(method, 0) + 1
        
        # 时间分布（按小时统计）
        hour = event.timestamp.hour
        agg["time_distribution"][hour] = agg["time_distribution"].get(hour, 0) + 1
        
        # 受影响组件
        agg["affected_components"].add(f"{event.component}:{event.component_type.value}")
        
        # 相关链路追踪
        if event.trace_id:
            agg["related_traces"].add(event.trace_id)
        
        # 置信度统计
        agg["total_confidence"] += event.confidence
        agg["avg_confidence"] = agg["total_confidence"] / group.occurrence_count
        
        # 转换set为list以便JSON序列化
        agg["affected_components"] = list(agg["affected_components"])
        agg["related_traces"] = list(agg["related_traces"])
    
    def _get_severity_level(self, severity: EventSeverity) -> int:
        """获取严重程度数值"""
        severity_levels = {
            EventSeverity.INFO: 1,
            EventSeverity.WARN: 2,
            EventSeverity.MINOR: 3,
            EventSeverity.MAJOR: 4,
            EventSeverity.CRITICAL: 5
        }
        return severity_levels.get(severity, 0)
    
    def get_event_groups_by_frequency(self, min_frequency: int = 5) -> List[EventGroup]:
        """获取高频事件分组"""
        return [
            group for group in self.event_groups.values() 
            if group.occurrence_count >= min_frequency
        ]
    
    def get_event_groups_in_time_window(self, start_time: datetime, end_time: datetime) -> List[EventGroup]:
        """获取时间窗口内的事件分组"""
        return [
            group for group in self.event_groups.values()
            if start_time <= group.last_seen <= end_time
        ]
    
    def cleanup_old_groups(self, ttl_hours: int = 24):
        """清理过期的事件分组"""
        cutoff_time = datetime.utcnow() - timedelta(hours=ttl_hours)
        old_fingerprints = [
            fingerprint for fingerprint, group in self.event_groups.items()
            if group.last_seen < cutoff_time
        ]
        
        for fingerprint in old_fingerprints:
            del self.event_groups[fingerprint]
        
        return len(old_fingerprints)
    
    def calculate_similarity(self, event1: UnifiedEvent, event2: UnifiedEvent) -> float:
        """计算两个事件的相似度"""
        # 服务相似度
        service_sim = 1.0 if event1.service == event2.service else 0.0
        
        # 组件相似度
        component_sim = 1.0 if event1.component == event2.component else 0.0
        
        # 事件类型相似度
        type_sim = 1.0 if event1.event_type == event2.event_type else 0.0
        
        # 消息相似度（基于词汇重叠）
        message_sim = self._calculate_message_similarity(event1.message, event2.message)
        
        # 命名空间相似度
        ns_sim = 1.0 if event1.namespace == event2.namespace else 0.0
        
        # 加权计算总相似度
        total_similarity = (
            service_sim * self.config.service_weight +
            component_sim * self.config.component_weight +
            type_sim * self.config.event_type_weight +
            message_sim * self.config.message_weight +
            ns_sim * self.config.namespace_weight
        )
        
        return min(total_similarity, 1.0)
    
    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """计算消息相似度"""
        tokens1 = set(self._tokenize_message(msg1))
        tokens2 = set(self._tokenize_message(msg2))
        
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        
        # Jaccard相似度
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def get_deduplication_stats(self) -> Dict[str, Any]:
        """获取去重统计信息"""
        total_groups = len(self.event_groups)
        total_events = sum(group.occurrence_count for group in self.event_groups.values())
        avg_group_size = total_events / total_groups if total_groups > 0 else 0.0
        
        # 更新统计信息
        self.stats["avg_group_size"] = avg_group_size
        
        return {
            **self.stats,
            "current_active_groups": total_groups,
            "total_events_in_groups": total_events,
            "deduplication_rate": self.stats["total_duplicates_found"] / max(self.stats["total_events_processed"], 1),
            "top_frequent_groups": self._get_top_frequent_groups(limit=10)
        }
    
    def _get_top_frequent_groups(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最频繁的事件分组"""
        sorted_groups = sorted(
            self.event_groups.values(),
            key=lambda g: g.occurrence_count,
            reverse=True
        )[:limit]
        
        return [
            {
                "fingerprint": group.fingerprint,
                "occurrence_count": group.occurrence_count,
                "canonical_event": {
                    "event_type": group.canonical_event.event_type.value,
                    "service": group.canonical_event.service,
                    "component": group.canonical_event.component,
                    "message": group.canonical_event.message[:100] + "..." if len(group.canonical_event.message) > 100 else group.canonical_event.message,
                    "severity": group.canonical_event.severity.value
                },
                "first_seen": group.first_seen.isoformat(),
                "last_seen": group.last_seen.isoformat(),
                "time_span_minutes": (group.last_seen - group.first_seen).total_seconds() / 60
            }
            for group in sorted_groups
        ]
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats = {
            "total_events_processed": 0,
            "total_duplicates_found": 0,
            "total_groups_created": 0,
            "avg_group_size": 0.0
        }