import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from ..config import settings
from .falkordb_service import FalkorDBService

logger = logging.getLogger(__name__)

class MockGraphitiService:
    """Mock Graphiti service for testing without real API keys"""
    
    def __init__(self):
        self.episodes = []
        self.mock_nodes = [
            {
                'id': str(uuid.uuid4()),
                'name': 'Sample Entity',
                'type': 'entity',
                'content': 'This is a sample knowledge entity for testing',
                'properties': {'category': 'test'},
                'created_at': datetime.utcnow(),
                'updated_at': None
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Test Event',
                'type': 'event',
                'content': 'A test event that occurred',
                'properties': {'importance': 'high'},
                'created_at': datetime.utcnow(),
                'updated_at': None
            }
        ]
        
    async def initialize(self):
        """Initialize mock service"""
        logger.info("Mock Graphiti service initialized successfully")
        
    async def close(self):
        """Close mock service"""
        pass
    
    async def add_episode(self, content: str, reference_time: Optional[datetime] = None) -> str:
        """Add new episode to mock knowledge graph"""
        episode_id = str(uuid.uuid4())
        episode = {
            'id': episode_id,
            'content': content,
            'reference_time': reference_time or datetime.utcnow(),
            'created_at': datetime.utcnow()
        }
        self.episodes.append(episode)
        logger.info(f"Added mock episode: {episode_id}")
        return episode_id
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for nodes in mock knowledge graph"""
        # Simple mock search - return nodes that contain query terms
        results = []
        query_lower = query.lower()
        
        for node in self.mock_nodes:
            if (query_lower in node['name'].lower() or 
                query_lower in node['content'].lower() or 
                query == ""):  # Return all nodes for empty query
                results.append(node)
                if len(results) >= limit:
                    break
        
        logger.info(f"Mock search returned {len(results)} nodes for query: {query}")
        return results
    
    async def get_node_relations(self, node_id: str) -> List[Dict[str, Any]]:
        """Get relations for a specific node"""
        # Return mock relations
        relations = [
            {
                'id': str(uuid.uuid4()),
                'source_id': node_id,
                'target_id': str(uuid.uuid4()),
                'relation_type': 'related_to',
                'description': 'Mock relation',
                'weight': 1.0,
                'properties': {},
                'created_at': datetime.utcnow(),
                'updated_at': None
            }
        ]
        return relations
    
    async def query_temporal(self, query: str, timestamp: Optional[datetime] = None, limit: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Perform temporal query on mock knowledge graph"""
        nodes = await self.search_nodes(query, limit)
        relations = []
        
        # Add some mock relations if nodes found
        if nodes:
            relations = await self.get_node_relations(nodes[0]['id'])
        
        return nodes, relations
    
    async def process_chat_query(self, message: str, session_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Process chat message and return response with optional knowledge graph results"""
        # Add the message as an episode
        await self.add_episode(f"User query: {message}")
        
        # Search for relevant knowledge
        nodes = await self.search_nodes(message, limit=5)
        
        # Generate response
        if nodes:
            response = f"Based on your query '{message}', I found {len(nodes)} relevant knowledge items. "
            response += "Here's what I know: " + ", ".join([node['name'] for node in nodes[:3]])
            
            query_result = {
                'nodes': nodes,
                'relations': [],
                'confidence': 0.8,
                'explanation': f"Found {len(nodes)} relevant nodes based on mock search"
            }
        else:
            response = "I don't have specific knowledge about that topic yet. This is a mock response for testing."
            query_result = None
        
        return response, query_result


class GraphitiService:
    """Enhanced Graphiti service with FalkorDB integration"""
    
    def __init__(self):
        self.graphiti = None
        self.falkordb = None
        self.use_mock = False
        self.mock_service = None
        
    async def initialize(self):
        """Initialize Graphiti client and FalkorDB integration"""
        # Initialize FalkorDB service
        try:
            self.falkordb = FalkorDBService()
            await self.falkordb.initialize()
            logger.info("FalkorDB service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FalkorDB service: {e}")
        
        # Check if we should use mock service for Graphiti
        api_key = settings.openai_api_key
        if not api_key or api_key.startswith('sk-test-') or api_key == 'your_openai_api_key_here':
            logger.info("Using mock Graphiti service (no valid API key)")
            self.use_mock = True
            self.mock_service = MockGraphitiService()
            await self.mock_service.initialize()
            return
            
        try:
            from graphiti import Graphiti
            from graphiti.nodes import EpisodeType
            
            self.graphiti = Graphiti()
            await self.graphiti.build_indices_if_needed()
            logger.info("Real Graphiti service initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize real Graphiti service, using mock: {e}")
            self.use_mock = True
            self.mock_service = MockGraphitiService()
            await self.mock_service.initialize()
    
    async def close(self):
        """Close Graphiti and FalkorDB connections"""
        if self.use_mock and self.mock_service:
            await self.mock_service.close()
        elif self.graphiti:
            await self.graphiti.close()
        
        if self.falkordb:
            await self.falkordb.close()
    
    async def add_episode(self, content: str, reference_time: Optional[datetime] = None) -> str:
        """Add new episode to knowledge graph"""
        episode_id = str(uuid.uuid4())
        
        # Store in FalkorDB if available
        if self.falkordb and self.falkordb.connected:
            try:
                await self.falkordb.create_node(
                    "Episode",
                    {
                        'name': f"Episode_{episode_id}",
                        'type': 'episode',
                        'content': content,
                        'reference_time': (reference_time or datetime.utcnow()).isoformat()
                    }
                )
            except Exception as e:
                logger.error(f"Failed to store episode in FalkorDB: {e}")
        
        # Use mock or real Graphiti
        if self.use_mock:
            return await self.mock_service.add_episode(content, reference_time)
            
        if not self.graphiti:
            raise RuntimeError("Graphiti service not initialized")
        
        try:
            from graphiti.nodes import EpisodeType
            episode = await self.graphiti.add_episode(
                name=f"Episode_{episode_id}",
                episode_body=content,
                reference_time=reference_time or datetime.utcnow(),
                episode_type=EpisodeType.text
            )
            logger.info(f"Added episode: {episode_id}")
            return episode_id
        except Exception as e:
            logger.error(f"Failed to add episode: {e}")
            raise
    
    async def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for nodes in knowledge graph"""
        nodes = []
        
        # Search in FalkorDB if available
        if self.falkordb and self.falkordb.connected:
            try:
                falkor_nodes = await self.falkordb.search_nodes(query, limit=limit)
                nodes.extend(falkor_nodes)
            except Exception as e:
                logger.error(f"Failed to search in FalkorDB: {e}")
        
        # If we got results from FalkorDB, return them
        if nodes:
            return nodes
        
        # Fallback to mock or real Graphiti
        if self.use_mock:
            return await self.mock_service.search_nodes(query, limit)
            
        if not self.graphiti:
            raise RuntimeError("Graphiti service not initialized")
        
        try:
            results = await self.graphiti.search(
                query=query,
                limit=limit
            )
            
            nodes = []
            for result in results:
                if hasattr(result, 'node') and result.node:
                    node_data = {
                        'id': str(result.node.uuid),
                        'name': getattr(result.node, 'name', 'Unknown'),
                        'type': result.node.__class__.__name__.lower(),
                        'content': getattr(result.node, 'summary', ''),
                        'properties': {},
                        'created_at': getattr(result.node, 'created_at', datetime.utcnow()),
                        'updated_at': getattr(result.node, 'updated_at', None)
                    }
                    nodes.append(node_data)
            
            return nodes
        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            raise
    
    async def get_node_relations(self, node_id: str) -> List[Dict[str, Any]]:
        """Get relations for a specific node"""
        # Try FalkorDB first
        if self.falkordb and self.falkordb.connected:
            try:
                return await self.falkordb.get_node_relationships(node_id)
            except Exception as e:
                logger.error(f"Failed to get relationships from FalkorDB: {e}")
        
        # Fallback to mock or real Graphiti
        if self.use_mock:
            return await self.mock_service.get_node_relations(node_id)
            
        if not self.graphiti:
            raise RuntimeError("Graphiti service not initialized")
        
        try:
            # This is a simplified implementation
            # In a full implementation, you'd query the graph database directly
            relations = []
            return relations
        except Exception as e:
            logger.error(f"Failed to get node relations: {e}")
            raise
    
    async def query_temporal(self, query: str, timestamp: Optional[datetime] = None, limit: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Perform temporal query on knowledge graph"""
        # Try FalkorDB first for better temporal support
        if self.falkordb and self.falkordb.connected:
            try:
                nodes = await self.falkordb.search_nodes(query, limit=limit)
                relations = []
                
                # Get relationships for found nodes
                for node in nodes[:3]:  # Limit to avoid too many queries
                    try:
                        node_relations = await self.falkordb.get_node_relationships(node['id'])
                        relations.extend(node_relations)
                    except Exception as e:
                        logger.error(f"Failed to get relations for node {node['id']}: {e}")
                
                return nodes, relations
            except Exception as e:
                logger.error(f"Failed temporal query in FalkorDB: {e}")
        
        # Fallback to mock or real Graphiti
        if self.use_mock:
            return await self.mock_service.query_temporal(query, timestamp, limit)
            
        if not self.graphiti:
            raise RuntimeError("Graphiti service not initialized")
        
        try:
            results = await self.graphiti.search(
                query=query,
                reference_time=timestamp,
                limit=limit
            )
            
            nodes = []
            relations = []
            
            for result in results:
                if hasattr(result, 'node') and result.node:
                    node_data = {
                        'id': str(result.node.uuid),
                        'name': getattr(result.node, 'name', 'Unknown'),
                        'type': result.node.__class__.__name__.lower(),
                        'content': getattr(result.node, 'summary', ''),
                        'properties': {},
                        'created_at': getattr(result.node, 'created_at', datetime.utcnow()),
                        'updated_at': getattr(result.node, 'updated_at', None)
                    }
                    nodes.append(node_data)
            
            return nodes, relations
        except Exception as e:
            logger.error(f"Failed to perform temporal query: {e}")
            raise
    
    async def process_chat_query(self, message: str, session_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Process chat message and return response with optional knowledge graph results"""
        # Add the message as an episode
        await self.add_episode(f"User query: {message}")
        
        # Search for relevant knowledge
        nodes = await self.search_nodes(message, limit=5)
        
        # Get graph statistics
        stats = {'nodes': 0, 'relationships': 0}
        if self.falkordb and self.falkordb.connected:
            try:
                stats = await self.falkordb.get_graph_stats()
            except Exception as e:
                logger.error(f"Failed to get graph stats: {e}")
        
        # Generate response
        if nodes:
            response = f"Based on your query '{message}', I found {len(nodes)} relevant knowledge items from a graph with {stats['nodes']} nodes and {stats['relationships']} relationships. "
            response += "Here's what I know: " + ", ".join([node['name'] for node in nodes[:3]])
            
            query_result = {
                'nodes': nodes,
                'relations': [],
                'confidence': 0.8,
                'explanation': f"Found {len(nodes)} relevant nodes using FalkorDB graph database search"
            }
        else:
            if self.use_mock:
                response = "I don't have specific knowledge about that topic yet. This is a mock response for testing."
            else:
                response = f"I don't have specific knowledge about that topic yet. The graph currently contains {stats['nodes']} nodes. Could you provide more context?"
            query_result = None
        
        return response, query_result