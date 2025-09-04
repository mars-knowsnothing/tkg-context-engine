#!/usr/bin/env python3
"""
运维事件数据导入脚本 - 将 graphiti_seed_all.jsonl 中的运维事件导入到 TKG Context Engine

该脚本处理运维监控场景的数据，包括：
- Service 服务节点
- Observation 监控观测数据 (APM/LB层面)
- API 接口节点
- K8sEvent Kubernetes事件
- 节点间的关系映射（EMITTED_OBS, HAS_ENDPOINT, IMPACTS等）

运维事件分析场景涵盖：
1. 服务健康监控 (Service Health)
2. API性能分析 (API Performance) 
3. 错误率异常检测 (Error Rate Analysis)
4. 系统可用性分析 (Availability Analysis)
5. 时序关联分析 (Temporal Correlation)
"""

import json
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API 配置
API_BASE_URL = "http://localhost:8001"
SEED_DATA_FILE = "../data/graphiti_seed_all.jsonl"

class TKGDataImporter:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def parse_jsonl_file(self, file_path: str):
        """解析 JSONL 文件，返回运维事件数据"""
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
            logger.error(f"种子数据文件未找到: {file_path}")
            return []
            
        logger.info(f"成功解析 {len(events)} 个运维事件")
        return events

    def convert_to_knowledge_node(self, event: dict) -> dict:
        """将 graphiti 事件转换为 TKG 知识节点格式"""
        op = event.get('op')
        
        if op == 'merge_node':
            # 处理节点数据
            node_type = event.get('type', 'Unknown')
            node_id = event.get('id', '')
            properties = event.get('properties', {})
            
            # 根据节点类型确定 TKG 节点类型
            tkg_type = self.map_node_type(node_type)
            
            # 生成节点名称
            name = self.generate_node_name(node_type, node_id, properties)
            
            # 构建节点内容描述
            content = self.generate_node_content(node_type, node_id, properties)
            
            # 构建时序信息
            valid_time = None
            if properties.get('time') or properties.get('valid_from'):
                start_time = properties.get('time') or properties.get('valid_from')
                end_time = properties.get('valid_to')
                
                # 转换时间格式
                if start_time and isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    except:
                        start_time = None
                
                if end_time and isinstance(end_time, str):
                    try:
                        # 如果是默认的远未来时间，设为None
                        if end_time == '9999-12-31T23:59:59+00:00':
                            end_time = None
                        else:
                            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    except:
                        end_time = None
                
                if start_time:
                    valid_time = {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat() if end_time else None
                    }
            
            return {
                "name": name,
                "type": tkg_type,
                "content": content,
                "properties": {
                    "original_type": node_type,
                    "original_id": node_id,
                    "source": "运维监控",
                    "category": self.get_category(node_type),
                    **properties
                },
                "valid_time": valid_time,
                "effective_time": properties.get('time')
            }
        
        elif op == 'merge_edge':
            # 处理关系数据 - 转换为关系记录
            return {
                "relation_type": event.get('type', 'RELATED'),
                "from_id": event.get('from_id', ''),
                "to_id": event.get('to_id', ''),
                "properties": event.get('properties', {}),
                "is_edge": True
            }
            
        return None

    def map_node_type(self, original_type: str) -> str:
        """映射原始节点类型到 TKG 节点类型"""
        type_mapping = {
            'Service': 'entity',
            'Observation': 'event', 
            'API': 'concept',
            'K8sEvent': 'event'
        }
        return type_mapping.get(original_type, 'concept')

    def get_category(self, node_type: str) -> str:
        """获取节点分类"""
        category_mapping = {
            'Service': '微服务',
            'Observation': '监控数据',
            'API': 'API接口',
            'K8sEvent': 'K8s事件'
        }
        return category_mapping.get(node_type, '其他')

    def generate_node_name(self, node_type: str, node_id: str, properties: dict) -> str:
        """生成节点名称"""
        if node_type == 'Service':
            service_name = properties.get('service_name', node_id)
            env = properties.get('env', '')
            return f"{service_name}-{env}" if env else service_name
        
        elif node_type == 'Observation':
            source = properties.get('source', 'Unknown')
            layer = properties.get('layer', 'Unknown')
            service = properties.get('service', 'Unknown')
            return f"{source}_{layer}_{service}_监控"
        
        elif node_type == 'API':
            route = properties.get('route', 'Unknown')
            method = properties.get('method', 'Unknown')
            return f"{method}_{route.replace('/', '_')}"
        
        elif node_type == 'K8sEvent':
            service = properties.get('service', 'Unknown')
            return f"{service}_K8s事件"
        
        return f"{node_type}_{node_id.split(':')[-1]}"

    def generate_node_content(self, node_type: str, node_id: str, properties: dict) -> str:
        """根据节点类型生成内容描述"""
        if node_type == 'Service':
            service_name = properties.get('service_name', node_id)
            env = properties.get('env', 'Unknown')
            project = properties.get('project', 'Unknown')
            return f"微服务 {service_name} 运行在 {env} 环境，隶属于 {project} 项目"
        
        elif node_type == 'Observation':
            source = properties.get('source', 'Unknown')
            layer = properties.get('layer', 'Unknown')
            service = properties.get('service', 'Unknown')
            time = properties.get('time', 'Unknown')
            error_rate = properties.get('error_rate', 0)
            latency = properties.get('latency_ms', 0)
            
            return f"{source} 在 {layer} 层监控到服务 {service} 在 {time} 的性能指标：错误率 {error_rate:.3%}，延迟 {latency}ms"
        
        elif node_type == 'API':
            route = properties.get('route', 'Unknown')
            method = properties.get('method', 'Unknown')
            return f"API接口 {method} {route}"
        
        elif node_type == 'K8sEvent':
            service = properties.get('service', 'Unknown')
            pod_status = properties.get('pod_status', 'Unknown')
            message = properties.get('message', 'Unknown')
            time = properties.get('time', 'Unknown')
            return f"Kubernetes事件：服务 {service} 在 {time} 发生异常，Pod状态 {pod_status}，详情：{message}"
        
        return f"{node_type} 节点: {node_id}"

    async def create_knowledge_node(self, node_data: dict) -> dict:
        """调用 TKG API 创建知识节点"""
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/knowledge/",
                json=node_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"成功创建节点: {result.get('content', '')[:50]}...")
            return result
        except httpx.HTTPError as e:
            logger.error(f"创建节点失败: {e}")
            return None

    async def import_seed_data(self):
        """导入种子数据的主流程"""
        logger.info("开始导入运维事件数据...")
        
        # 解析种子数据文件
        events = self.parse_jsonl_file(SEED_DATA_FILE)
        if not events:
            logger.error("没有找到有效的种子数据")
            return
        
        # 分离节点和边
        nodes = [event for event in events if event.get('op') == 'merge_node']
        edges = [event for event in events if event.get('op') == 'merge_edge']
        
        logger.info(f"发现 {len(nodes)} 个节点，{len(edges)} 条关系")
        
        # 创建节点映射
        created_nodes = {}
        
        # 第一阶段：创建所有节点
        logger.info("第一阶段：创建知识节点...")
        for i, node_event in enumerate(nodes, 1):
            node_data = self.convert_to_knowledge_node(node_event)
            if node_data and not node_data.get('is_edge'):
                original_id = node_event.get('id')
                created_node = await self.create_knowledge_node(node_data)
                if created_node:
                    created_nodes[original_id] = created_node
                    logger.info(f"进度: {i}/{len(nodes)} - {node_data.get('properties', {}).get('category', 'Unknown')}")
                
                # 避免请求过快
                await asyncio.sleep(0.1)
        
        logger.info(f"第一阶段完成：成功创建 {len(created_nodes)} 个节点")
        
        # 第二阶段：建立关系（可选，需要关系管理API）
        logger.info("第二阶段：建立节点关系...")
        relation_count = 0
        for edge_event in edges:
            from_id = edge_event.get('from_id')
            to_id = edge_event.get('to_id')
            
            if from_id in created_nodes and to_id in created_nodes:
                # 这里可以调用关系创建API，暂时跳过
                relation_count += 1
                logger.debug(f"关系: {edge_event.get('type')} {from_id} -> {to_id}")
        
        logger.info(f"发现 {relation_count} 条有效关系（节点关系建立需要关系API）")
        
        # 输出统计信息
        await self.print_import_summary(created_nodes)
        
        logger.info("运维事件数据导入完成！")

    async def print_import_summary(self, created_nodes: dict):
        """打印导入统计摘要"""
        logger.info("=" * 60)
        logger.info("数据导入统计摘要")
        logger.info("=" * 60)
        
        # 按类型统计
        type_stats = {}
        category_stats = {}
        
        for node in created_nodes.values():
            node_type = node.get('type', 'unknown')
            category = node.get('properties', {}).get('category', '其他')
            
            type_stats[node_type] = type_stats.get(node_type, 0) + 1
            category_stats[category] = category_stats.get(category, 0) + 1
        
        logger.info("按节点类型统计:")
        for node_type, count in type_stats.items():
            logger.info(f"  {node_type}: {count} 个")
        
        logger.info("按业务分类统计:")
        for category, count in category_stats.items():
            logger.info(f"  {category}: {count} 个")
        
        logger.info(f"总计导入节点: {len(created_nodes)} 个")
        logger.info("=" * 60)

async def main():
    """主函数"""
    logger.info("TKG Context Engine - 运维事件数据导入工具")
    logger.info("目标场景：运维事件分析和时序关联")
    
    async with TKGDataImporter(API_BASE_URL) as importer:
        try:
            # 检查API连通性
            response = await importer.client.get(f"{API_BASE_URL}/health")
            if response.status_code != 200:
                logger.error("后端API不可用，请确认服务已启动")
                return
            logger.info("✅ 后端API连接正常")
            
            # 执行数据导入
            await importer.import_seed_data()
            
        except Exception as e:
            logger.error(f"导入过程中发生错误: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())