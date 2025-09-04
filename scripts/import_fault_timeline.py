#!/usr/bin/env python3
"""
故障时序事件导入脚本 - 导入完整的故障发生和恢复时间线

该脚本专门处理运维故障场景的时序事件，包括：
- 故障检测与告警 (FaultEvent, Alert)
- 影响扩散观测 (Observation, K8sEvent)
- 事故响应流程 (IncidentResponse, DiagnosticAction)
- 恢复处理过程 (RecoveryAction, RecoveryValidation)
- 事故解决复盘 (IncidentResolution, PostMortem)

支持时序查询场景：
1. 故障影响时间线分析
2. 响应效率评估 (MTTD, MTTR)
3. 根因分析路径追踪
4. 恢复策略有效性验证
"""

import json
import asyncio
import httpx
from datetime import datetime, timedelta
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API 配置
API_BASE_URL = "http://localhost:8001"
FAULT_DATA_FILE = "../data/fault_timeline_events.jsonl"

class FaultTimelineImporter:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def parse_fault_events(self, file_path: str):
        """解析故障时序事件文件"""
        events = []
        file_path = Path(__file__).parent / file_path
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第 {line_num} 行 JSON 解析错误: {e}")
                        continue
        except FileNotFoundError:
            logger.error(f"故障事件数据文件未找到: {file_path}")
            return []
            
        logger.info(f"成功解析 {len(events)} 个故障时序事件")
        return events

    def convert_fault_event_to_knowledge_node(self, event: dict) -> dict:
        """将故障事件转换为知识节点"""
        op = event.get('op')
        
        if op == 'merge_node':
            node_type = event.get('type', 'Unknown')
            node_id = event.get('id', '')
            properties = event.get('properties', {})
            
            # 生成节点名称和内容
            name = self.generate_fault_node_name(node_type, properties)
            content = self.generate_fault_node_content(node_type, properties)
            tkg_type = self.map_fault_node_type(node_type)
            
            # 时序信息处理
            valid_time = None
            time_str = properties.get('time')
            if time_str:
                try:
                    start_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    # 为不同事件类型设置不同的有效期
                    end_time = self.calculate_event_validity_end(node_type, start_time)
                    
                    valid_time = {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat() if end_time else None
                    }
                except Exception as e:
                    logger.warning(f"时间解析错误: {e}")
            
            return {
                "name": name,
                "type": tkg_type,
                "content": content,
                "properties": {
                    "fault_category": self.get_fault_category(node_type),
                    "original_type": node_type,
                    "original_id": node_id,
                    "source": "故障管理系统",
                    "timeline_phase": self.get_timeline_phase(node_type),
                    **properties
                },
                "valid_time": valid_time,
                "effective_time": properties.get('time')
            }
        
        return None

    def map_fault_node_type(self, original_type: str) -> str:
        """映射故障节点类型"""
        type_mapping = {
            'FaultEvent': 'event',
            'Alert': 'event', 
            'K8sEvent': 'event',
            'Observation': 'event',
            'IncidentResponse': 'episode',
            'DiagnosticAction': 'episode',
            'RecoveryAction': 'episode',
            'RecoveryValidation': 'episode',
            'IncidentResolution': 'episode',
            'PostMortem': 'concept'
        }
        return type_mapping.get(original_type, 'event')

    def get_fault_category(self, node_type: str) -> str:
        """获取故障分类"""
        category_mapping = {
            'FaultEvent': '故障检测',
            'Alert': '告警通知',
            'K8sEvent': 'K8s事件',
            'Observation': '监控观测',
            'IncidentResponse': '事故响应',
            'DiagnosticAction': '故障诊断',
            'RecoveryAction': '恢复处理',
            'RecoveryValidation': '恢复验证',
            'IncidentResolution': '事故解决',
            'PostMortem': '复盘分析'
        }
        return category_mapping.get(node_type, '其他')

    def get_timeline_phase(self, node_type: str) -> str:
        """获取时间线阶段"""
        phase_mapping = {
            'FaultEvent': '1-故障发生',
            'Alert': '2-告警触发',
            'K8sEvent': '3-系统响应',
            'Observation': '4-影响观测',
            'IncidentResponse': '5-事故响应',
            'DiagnosticAction': '6-问题诊断',
            'RecoveryAction': '7-恢复处理',
            'RecoveryValidation': '8-恢复验证',
            'IncidentResolution': '9-事故解决',
            'PostMortem': '10-复盘总结'
        }
        return phase_mapping.get(node_type, '0-未知阶段')

    def calculate_event_validity_end(self, node_type: str, start_time: datetime) -> datetime:
        """计算事件有效期结束时间"""
        duration_mapping = {
            'FaultEvent': timedelta(hours=24),  # 故障事件24小时有效
            'Alert': timedelta(hours=1),        # 告警1小时有效
            'K8sEvent': timedelta(minutes=30),  # K8s事件30分钟有效
            'Observation': timedelta(minutes=15), # 观测数据15分钟有效
            'IncidentResponse': timedelta(hours=8), # 响应8小时有效
            'DiagnosticAction': timedelta(hours=2), # 诊断2小时有效
            'RecoveryAction': timedelta(hours=1),   # 恢复1小时有效
            'RecoveryValidation': timedelta(hours=2), # 验证2小时有效
            'IncidentResolution': timedelta(days=30), # 解决方案30天有效
            'PostMortem': None  # 复盘长期有效
        }
        
        duration = duration_mapping.get(node_type)
        return start_time + duration if duration else None

    def generate_fault_node_name(self, node_type: str, properties: dict) -> str:
        """生成故障节点名称"""
        if node_type == 'FaultEvent':
            fault_id = properties.get('fault_id', 'UNKNOWN')
            fault_type = properties.get('fault_type', '未知故障')
            return f"{fault_id}_{fault_type}"
        
        elif node_type == 'Alert':
            alert_type = properties.get('alert_type', '未知告警')
            priority = properties.get('priority', 'P5')
            return f"{priority}_{alert_type}_告警"
        
        elif node_type == 'IncidentResponse':
            incident_id = properties.get('incident_id', 'UNKNOWN')
            team = properties.get('response_team', '未知团队')
            return f"{incident_id}_{team}_响应"
        
        elif node_type == 'RecoveryAction':
            action_type = properties.get('action_type', '恢复动作')
            return f"恢复操作_{action_type}"
        
        elif node_type == 'PostMortem':
            postmortem_id = properties.get('postmortem_id', 'UNKNOWN')
            return f"{postmortem_id}_复盘分析"
        
        else:
            service = properties.get('service', '未知服务')
            time_str = properties.get('time', '')
            time_part = time_str.split('T')[1][:8] if 'T' in time_str else 'unknown'
            return f"{service}_{node_type}_{time_part}"

    def generate_fault_node_content(self, node_type: str, properties: dict) -> str:
        """生成故障节点内容描述"""
        service = properties.get('service', '未知服务')
        time = properties.get('time', '未知时间')
        
        if node_type == 'FaultEvent':
            fault_type = properties.get('fault_type', '未知故障')
            severity = properties.get('severity', '未知严重程度')
            description = properties.get('description', '无描述')
            impact = properties.get('impact_level', '未知影响')
            return f"{time}: {service} 发生{severity}级故障 - {fault_type}。{description}。影响级别: {impact}"
        
        elif node_type == 'Alert':
            alert_type = properties.get('alert_type', '未知类型')
            threshold = properties.get('threshold', 0)
            current_value = properties.get('current_value', 0)
            message = properties.get('message', '无消息')
            return f"{time}: {service} 触发{alert_type}告警。阈值: {threshold}, 当前值: {current_value}。{message}"
        
        elif node_type == 'Observation':
            source = properties.get('source', '未知源')
            error_rate = properties.get('error_rate', 0)
            latency = properties.get('latency_ms', 0)
            status = properties.get('status', '未知状态')
            return f"{time}: {source} 监控显示 {service} 错误率 {error_rate:.2%}, 延迟 {latency}ms, 状态: {status}"
        
        elif node_type == 'IncidentResponse':
            incident_id = properties.get('incident_id', '未知事故')
            team = properties.get('response_team', '未知团队')
            priority = properties.get('priority', '未知优先级')
            impact = properties.get('estimated_impact', '未知影响')
            return f"{time}: {incident_id} 事故响应启动，{team} 团队接手处理。优先级: {priority}, 预估影响: {impact}"
        
        elif node_type == 'DiagnosticAction':
            action_type = properties.get('action_type', '未知诊断')
            result = properties.get('result', '无结果')
            details = properties.get('details', '无详情')
            next_action = properties.get('next_action', '无后续动作')
            return f"{time}: 执行{action_type}诊断，结果: {result}。{details}。下一步: {next_action}"
        
        elif node_type == 'RecoveryAction':
            action_type = properties.get('action_type', '未知恢复')
            status = properties.get('status', '未知状态')
            duration = properties.get('estimated_duration', '未知时长')
            risk = properties.get('risk_level', '未知风险')
            return f"{time}: 执行{action_type}恢复操作，状态: {status}，预计耗时: {duration}，风险级别: {risk}"
        
        elif node_type == 'RecoveryValidation':
            validation_type = properties.get('validation_type', '未知验证')
            success_rate = properties.get('success_rate', 0)
            status = properties.get('status', '未知状态')
            test_cases = properties.get('test_cases', [])
            return f"{time}: 执行{validation_type}验证，成功率: {success_rate:.1%}，状态: {status}。测试用例: {', '.join(test_cases)}"
        
        elif node_type == 'IncidentResolution':
            incident_id = properties.get('incident_id', '未知事故')
            downtime = properties.get('total_downtime', '未知时长')
            root_cause = properties.get('root_cause', '未知根因')
            fix = properties.get('fix_applied', '未知修复')
            return f"{time}: {incident_id} 事故解决，总停机时间: {downtime}。根因: {root_cause}。修复方案: {fix}"
        
        elif node_type == 'PostMortem':
            incident_id = properties.get('incident_id', '未知事故')
            root_cause = properties.get('root_cause_analysis', '无根因分析')
            prevention = properties.get('prevention_actions', [])
            lessons = properties.get('lessons_learned', '无经验教训')
            return f"{time}: {incident_id} 复盘分析完成。根因: {root_cause}。预防措施: {', '.join(prevention)}。经验教训: {lessons}"
        
        elif node_type == 'K8sEvent':
            event_type = properties.get('event_type', '未知事件')
            pod_status = properties.get('pod_status', '未知状态')
            message = properties.get('message', '无消息')
            return f"{time}: {service} K8s {event_type} 事件，Pod状态: {pod_status}。{message}"
        
        return f"{time}: {service} {node_type} 事件 - {properties}"

    async def create_fault_knowledge_node(self, node_data: dict) -> dict:
        """创建故障知识节点"""
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/knowledge/",
                json=node_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            # 记录详细的创建信息
            phase = result.get('properties', {}).get('timeline_phase', 'Unknown')
            category = result.get('properties', {}).get('fault_category', 'Unknown')
            logger.info(f"✅ 创建节点: [{phase}] {category} - {result.get('name', '')}")
            return result
        except httpx.HTTPError as e:
            logger.error(f"❌ 创建节点失败: {e}")
            return None

    async def import_fault_timeline(self):
        """导入故障时序事件"""
        logger.info("🚀 开始导入故障时序事件数据...")
        
        # 解析事件文件
        events = self.parse_fault_events(FAULT_DATA_FILE)
        if not events:
            logger.error("❌ 没有找到有效的故障事件数据")
            return
        
        # 分离节点和边
        nodes = [event for event in events if event.get('op') == 'merge_node']
        edges = [event for event in events if event.get('op') == 'merge_edge']
        
        logger.info(f"📊 发现 {len(nodes)} 个时序节点，{len(edges)} 条因果关系")
        
        # 按时间排序，确保时序正确性
        nodes.sort(key=lambda x: x.get('properties', {}).get('time', ''))
        
        # 创建节点映射
        created_nodes = {}
        timeline_stats = {}
        
        # 导入所有故障时序节点
        logger.info("📅 阶段一：按时间顺序创建故障时序节点...")
        for i, node_event in enumerate(nodes, 1):
            node_data = self.convert_fault_event_to_knowledge_node(node_event)
            if node_data:
                # 统计时间线阶段
                phase = node_data.get('properties', {}).get('timeline_phase', 'Unknown')
                timeline_stats[phase] = timeline_stats.get(phase, 0) + 1
                
                # 创建节点
                original_id = node_event.get('id')
                created_node = await self.create_fault_knowledge_node(node_data)
                if created_node:
                    created_nodes[original_id] = created_node
                    
                    # 显示进度和时序信息
                    time_info = node_data.get('properties', {}).get('time', 'Unknown')
                    category = node_data.get('properties', {}).get('fault_category', 'Unknown')
                    logger.info(f"⏰ 进度: {i}/{len(nodes)} - {time_info} - {category}")
                
                # 控制导入速度
                await asyncio.sleep(0.1)
        
        logger.info(f"✅ 阶段一完成：成功创建 {len(created_nodes)} 个时序节点")
        
        # 输出时间线统计
        await self.print_timeline_summary(created_nodes, timeline_stats, edges)
        
        logger.info("🎉 故障时序事件导入完成！")
        logger.info("💡 现在可以使用时序查询功能分析故障影响链和恢复过程")

    async def print_timeline_summary(self, created_nodes: dict, timeline_stats: dict, edges: list):
        """打印时间线统计摘要"""
        logger.info("=" * 80)
        logger.info("📊 故障时序事件导入统计摘要")
        logger.info("=" * 80)
        
        # 时间线阶段统计
        logger.info("🔢 按时间线阶段统计:")
        for phase, count in sorted(timeline_stats.items()):
            logger.info(f"  {phase}: {count} 个事件")
        
        # 故障分类统计
        category_stats = {}
        for node in created_nodes.values():
            category = node.get('properties', {}).get('fault_category', '其他')
            category_stats[category] = category_stats.get(category, 0) + 1
        
        logger.info("🏷️  按故障分类统计:")
        for category, count in category_stats.items():
            logger.info(f"  {category}: {count} 个")
        
        # 时序关系统计
        logger.info(f"🔗 因果关系: {len(edges)} 条时序关联")
        
        # 时间范围
        times = []
        for node in created_nodes.values():
            time_str = node.get('properties', {}).get('time')
            if time_str:
                try:
                    times.append(datetime.fromisoformat(time_str.replace('Z', '+00:00')))
                except:
                    pass
        
        if times:
            times.sort()
            start_time = times[0]
            end_time = times[-1]
            duration = end_time - start_time
            
            logger.info(f"⏳ 故障时间线范围:")
            logger.info(f"  开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  总时长: {duration}")
        
        logger.info(f"📈 总计导入时序节点: {len(created_nodes)} 个")
        logger.info("=" * 80)
        
        # 查询建议
        logger.info("🔍 推荐时序查询场景:")
        logger.info("  1. 在 Temporal Explorer 中设置时间范围: 2025-09-01T08:15:00 ~ 08:35:00")
        logger.info("  2. Chat 查询: '分析 2025年9月1日上午的故障时间线'")
        logger.info("  3. Chat 查询: '故障恢复过程的各个阶段用了多长时间？'")
        logger.info("  4. Chat 查询: 'MTTD和MTTR分别是多少？'")
        logger.info("  5. Chat 查询: '根因分析的结论是什么？'")

async def main():
    """主函数"""
    logger.info("🔥 TKG Context Engine - 故障时序事件导入工具")
    logger.info("🎯 目标场景：故障影响链分析、MTTD/MTTR计算、根因追踪")
    
    async with FaultTimelineImporter(API_BASE_URL) as importer:
        try:
            # 检查API连通性
            response = await importer.client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                logger.error("❌ 后端API不可用，请确认服务已启动")
                return
            logger.info("✅ 后端API连接正常")
            
            # 执行数据导入
            await importer.import_fault_timeline()
            
        except Exception as e:
            logger.error(f"❌ 导入过程中发生错误: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())