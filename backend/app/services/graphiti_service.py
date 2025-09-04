import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from ..config import settings
from .falkordb_service import FalkorDBService

logger = logging.getLogger(__name__)

class GraphitiService:
    """Graph database service using FalkorDB as primary storage"""
    
    def __init__(self):
        self.falkordb = None
        
    async def initialize(self):
        """Initialize FalkorDB service as primary graph database"""
        try:
            self.falkordb = FalkorDBService()
            await self.falkordb.initialize()
            
            if not self.falkordb.connected:
                raise RuntimeError("FalkorDB service failed to connect")
                
            logger.info("GraphitiService initialized with FalkorDB successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GraphitiService: {e}")
            raise RuntimeError(f"GraphitiService initialization failed: {e}")
    
    async def close(self):
        """Close FalkorDB connections"""
        if self.falkordb:
            await self.falkordb.close()
    
    async def create_node(self, name: str, content: str, node_type: str = 'entity', properties: Optional[Dict[str, Any]] = None) -> str:
        """Create a new node in the graph database"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            node_id = await self.falkordb.create_node(
                node_type.capitalize(),  # Convert to proper case for labels
                {
                    'name': name,
                    'type': node_type,
                    'content': content,
                    **(properties or {})
                }
            )
            logger.info(f"Created node: {node_id} of type {node_type}")
            return node_id
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            raise
    
    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific node by ID"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            node = await self.falkordb.get_node(node_id)
            return node
        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            raise
    
    async def update_node(self, node_id: str, name: Optional[str] = None, content: Optional[str] = None, 
                         node_type: Optional[str] = None, properties: Optional[Dict[str, Any]] = None) -> bool:
        """Update a node in the graph database"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if content is not None:
                update_data['content'] = content
            if node_type is not None:
                update_data['type'] = node_type
            if properties is not None:
                update_data.update(properties)
            
            if not update_data:
                return True  # Nothing to update
            
            success = await self.falkordb.update_node(node_id, update_data)
            if success:
                logger.info(f"Updated node: {node_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to update node {node_id}: {e}")
            raise
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node from the graph database"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            success = await self.falkordb.delete_node(node_id)
            if success:
                logger.info(f"Deleted node: {node_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
            raise
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for nodes in the graph database"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            nodes = await self.falkordb.search_nodes(query, limit=limit)
            logger.info(f"Search returned {len(nodes)} nodes for query: {query}")
            return nodes
        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            raise
    
    async def get_node_relations(self, node_id: str) -> List[Dict[str, Any]]:
        """Get relations for a specific node"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            relations = await self.falkordb.get_node_relationships(node_id)
            return relations
        except Exception as e:
            logger.error(f"Failed to get relationships for node {node_id}: {e}")
            raise
    
    async def get_graph_stats(self) -> Dict[str, int]:
        """Get graph statistics"""
        if not self.falkordb or not self.falkordb.connected:
            return {'nodes': 0, 'relationships': 0}
        
        try:
            stats = await self.falkordb.get_graph_stats()
            return stats
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {'nodes': 0, 'relationships': 0}
    
    async def create_relationship(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """Create a relationship between two nodes"""
        if not self.falkordb or not self.falkordb.connected:
            raise RuntimeError("FalkorDB service not available")
        
        try:
            rel_id = await self.falkordb.create_relationship(source_id, target_id, relation_type, properties)
            logger.info(f"Created relationship: {rel_id}")
            return rel_id
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise
    
    async def process_chat_query(self, message: str, session_id: str, limit: int = 20) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Process chat message and return response with knowledge graph results"""
        try:
            # Search for relevant knowledge - use same search strategy as temporal queries
            nodes = await self.search_nodes(message, limit=limit * 2)  # Get more results initially
            
            # Apply the same limiting strategy as temporal queries
            nodes = nodes[:limit]
            
            # Generate response based on found nodes
            if nodes:
                response = f"Based on your query '{message}', I found {len(nodes)} relevant knowledge items:\n"
                for i, node in enumerate(nodes[:3], 1):
                    response += f"{i}. {node['name']}: {node['content'][:100]}...\n"
                
                query_result = {
                    'nodes': nodes,
                    'relations': [],
                    'confidence': 0.8,
                    'explanation': f"Found {len(nodes)} relevant nodes in graph database"
                }
            else:
                response = "I couldn't find specific information about that topic in the knowledge graph. Would you like to add some knowledge about it?"
                query_result = None
            
            return response, query_result
        except Exception as e:
            logger.error(f"Failed to process chat query: {e}")
            return "Sorry, I encountered an error processing your query.", None