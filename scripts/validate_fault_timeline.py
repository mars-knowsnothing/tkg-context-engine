#!/usr/bin/env python3
"""
故障时序分析验证脚本 - 验证故障时间线查询和分析功能

验证场景包括：
1. 时序窗口查询 (relative time windows)
2. 故障影响链分析 (fault impact timeline) 
3. MTTD/MTTR计算验证 (metrics calculation)
4. 根因分析路径追踪 (root cause analysis)
5. 恢复过程完整性验证 (recovery validation)
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8001"

class FaultTimelineValidator:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def get_knowledge_nodes(self):
        """获取所有知识节点"""
        response = await self.client.get(f"{self.api_base_url}/api/knowledge/")
        response.raise_for_status()
        return response.json()

    async def search_knowledge(self, search_term: str):
        """搜索知识节点"""
        response = await self.client.get(
            f"{self.api_base_url}/api/knowledge/",
            params={"search": search_term}
        )
        response.raise_for_status()
        return response.json()

    async def temporal_query(self, query: str, start_time: str, end_time: str, limit: int = 20):
        """时序查询"""
        payload = {
            "query": query,
            "time_range": {
                "start_time": start_time,
                "end_time": end_time
            },
            "limit": limit
        }
        response = await self.client.post(
            f"{self.api_base_url}/api/temporal/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    async def chat_query(self, message: str):
        """聊天查询"""
        response = await self.client.post(
            f"{self.api_base_url}/api/chat/",
            json={"message": message}
        )
        response.raise_for_status()
        return response.json()

    def extract_fault_timeline_events(self, nodes):
        """提取故障时序事件"""
        fault_events = []
        for node in nodes:
            properties = node.get('properties', {})
            if properties.get('fault_category'):
                fault_events.append({
                    'name': node.get('name', ''),
                    'time': properties.get('time', ''),
                    'category': properties.get('fault_category', ''),
                    'phase': properties.get('timeline_phase', ''),
                    'content': node.get('content', ''),
                    'node_id': node.get('id', '')
                })
        
        # 按时间排序
        fault_events.sort(key=lambda x: x['time'])
        return fault_events

    def calculate_fault_metrics(self, fault_events):
        """计算故障指标 (MTTD, MTTR)"""
        fault_start = None
        alert_time = None
        resolution_time = None
        
        for event in fault_events:
            phase = event['phase']
            time_str = event['time']
            
            if not time_str:
                continue
                
            try:
                event_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            except:
                continue
                
            if '1-故障发生' in phase and fault_start is None:
                fault_start = event_time
            elif '2-告警触发' in phase and alert_time is None:
                alert_time = event_time
            elif '9-事故解决' in phase and resolution_time is None:
                resolution_time = event_time
        
        metrics = {}
        if fault_start and alert_time:
            mttd = (alert_time - fault_start).total_seconds()
            metrics['MTTD'] = f"{mttd}秒 ({mttd/60:.1f}分钟)"
        
        if fault_start and resolution_time:
            mttr = (resolution_time - fault_start).total_seconds()
            metrics['MTTR'] = f"{mttr}秒 ({mttr/60:.1f}分钟)"
        
        if alert_time and resolution_time:
            response_time = (resolution_time - alert_time).total_seconds()
            metrics['Response Time'] = f"{response_time}秒 ({response_time/60:.1f}分钟)"
        
        return metrics

    async def validate_basic_functionality(self):
        """验证基础功能"""
        logger.info("🔍 验证1: 基础数据完整性检查")
        
        # 获取所有节点
        all_nodes = await self.get_knowledge_nodes()
        logger.info(f"✅ 总节点数: {len(all_nodes)}")
        
        # 统计故障相关节点
        fault_nodes = [n for n in all_nodes if n.get('properties', {}).get('fault_category')]
        logger.info(f"✅ 故障时序节点数: {len(fault_nodes)}")
        
        # 按分类统计
        categories = {}
        for node in fault_nodes:
            category = node.get('properties', {}).get('fault_category', '其他')
            categories[category] = categories.get(category, 0) + 1
        
        logger.info("📊 故障节点分类统计:")
        for category, count in sorted(categories.items()):
            logger.info(f"   {category}: {count}个")
        
        return fault_nodes

    async def validate_search_functionality(self, fault_nodes):
        """验证搜索功能"""
        logger.info("🔍 验证2: 搜索功能测试")
        
        # 测试关键词搜索
        search_terms = ['FAULT-20250901-001', '数据库连接', 'CRITICAL', 'SRE-TEAM-A']
        
        for term in search_terms:
            try:
                results = await self.search_knowledge(term)
                logger.info(f"✅ 搜索'{term}': 找到{len(results)}个结果")
            except Exception as e:
                logger.error(f"❌ 搜索'{term}'失败: {e}")

    async def validate_temporal_queries(self, fault_events):
        """验证时序查询"""
        logger.info("🔍 验证3: 时序查询功能测试")
        
        if not fault_events:
            logger.error("❌ 没有故障事件数据，跳过时序查询测试")
            return
        
        # 定义查询时间窗口
        start_time = "2025-09-01T08:15:00+09:00"
        end_time = "2025-09-01T08:35:00+09:00"
        
        # 测试不同的时序查询
        queries = [
            "分析故障发生到恢复的完整时间线",
            "显示所有告警和系统响应事件",
            "列出恢复过程的各个阶段",
            "查找错误率相关的监控数据"
        ]
        
        for query in queries:
            try:
                result = await self.temporal_query(query, start_time, end_time)
                nodes_count = len(result.get('nodes', []))
                logger.info(f"✅ 时序查询'{query}': 返回{nodes_count}个节点")
                logger.info(f"   解释: {result.get('explanation', '无解释')[:100]}...")
            except Exception as e:
                logger.error(f"❌ 时序查询失败: {e}")

    async def validate_chat_analysis(self):
        """验证聊天分析功能"""
        logger.info("🔍 验证4: 聊天分析功能测试")
        
        # 测试故障分析查询
        analysis_queries = [
            "总结一下系统最近的故障情况",
            "分析数据库连接超时故障的影响",
            "什么时候开始出现错误率异常？",
            "SRE团队的响应时间如何？",
            "故障恢复过程顺利吗？"
        ]
        
        for query in analysis_queries:
            try:
                result = await self.chat_query(query)
                response = result.get('response', '无响应')
                logger.info(f"✅ 聊天查询'{query}'")
                logger.info(f"   回复: {response[:150]}...")
            except Exception as e:
                logger.error(f"❌ 聊天查询失败: {e}")

    async def validate_fault_timeline_analysis(self, fault_events):
        """验证故障时间线分析"""
        logger.info("🔍 验证5: 故障时间线分析")
        
        if not fault_events:
            logger.error("❌ 没有故障事件数据")
            return
        
        # 显示完整时间线
        logger.info("📅 完整故障时间线:")
        for event in fault_events:
            time_str = event['time'].split('T')[1][:8] if 'T' in event['time'] else 'Unknown'
            logger.info(f"   {time_str} | {event['phase']} | {event['category']} | {event['name']}")
        
        # 计算故障指标
        metrics = self.calculate_fault_metrics(fault_events)
        logger.info("📊 故障响应指标:")
        for metric, value in metrics.items():
            logger.info(f"   {metric}: {value}")
        
        # 分析时间线完整性
        phases = set(event['phase'] for event in fault_events)
        expected_phases = [
            '1-故障发生', '2-告警触发', '3-系统响应', '4-影响观测',
            '5-事故响应', '6-问题诊断', '7-恢复处理', '8-恢复验证', 
            '9-事故解决', '10-复盘总结'
        ]
        
        missing_phases = set(expected_phases) - phases
        if missing_phases:
            logger.warning(f"⚠️ 缺失的时间线阶段: {', '.join(missing_phases)}")
        else:
            logger.info("✅ 故障时间线完整，包含所有关键阶段")

    async def run_comprehensive_validation(self):
        """运行全面验证"""
        logger.info("🚀 故障时序分析功能全面验证开始")
        logger.info("=" * 80)
        
        try:
            # 验证1: 基础数据
            fault_nodes = await self.validate_basic_functionality()
            fault_events = self.extract_fault_timeline_events(fault_nodes)
            
            # 验证2: 搜索功能  
            await self.validate_search_functionality(fault_nodes)
            
            # 验证3: 时序查询
            await self.validate_temporal_queries(fault_events)
            
            # 验证4: 聊天分析
            await self.validate_chat_analysis()
            
            # 验证5: 故障时间线分析
            await self.validate_fault_timeline_analysis(fault_events)
            
            logger.info("=" * 80)
            logger.info("🎉 故障时序分析功能验证完成！")
            
            # 输出使用建议
            self.print_usage_recommendations()
            
        except Exception as e:
            logger.error(f"❌ 验证过程中发生错误: {e}")
            raise

    def print_usage_recommendations(self):
        """打印使用建议"""
        logger.info("💡 功能使用建议:")
        logger.info("   1. 打开前端界面: http://localhost:3002")
        logger.info("   2. 在Knowledge Manager中浏览22个节点数据")
        logger.info("   3. 在Temporal Explorer中设置时间范围：")
        logger.info("      开始: 2025-09-01T08:15:00+09:00")
        logger.info("      结束: 2025-09-01T08:35:00+09:00")
        logger.info("   4. 在Chat Interface中尝试以下查询：")
        logger.info("      - '分析FAULT-20250901-001故障的影响范围'")
        logger.info("      - '故障恢复用了多长时间？'")
        logger.info("      - '什么导致了数据库连接超时？'")
        logger.info("      - 'SRE团队的响应效率如何？'")
        logger.info("   5. 使用搜索功能查找特定事件：")
        logger.info("      - 搜索 'CRITICAL' 查看严重故障")
        logger.info("      - 搜索 'ERROR_RATE' 查看错误率相关事件")
        logger.info("      - 搜索 'Recovery' 查看恢复相关事件")

async def main():
    """主验证流程"""
    logger.info("🔥 TKG Context Engine - 故障时序分析验证工具")
    
    async with FaultTimelineValidator(API_BASE_URL) as validator:
        # 检查API连通性
        try:
            response = await validator.client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                logger.error("❌ 后端API不可用")
                return
            logger.info("✅ 后端API连接正常")
        except Exception as e:
            logger.error(f"❌ API连接失败: {e}")
            return
        
        # 运行验证
        await validator.run_comprehensive_validation()

if __name__ == "__main__":
    asyncio.run(main())