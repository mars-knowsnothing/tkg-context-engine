import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from ..config import settings

logger = logging.getLogger(__name__)

# Try to import FalkorDB, fall back to None if not available
try:
    from falkordb import FalkorDB as FalkorDBClient
    FALKORDB_AVAILABLE = True
except ImportError:
    logger.warning("FalkorDB not available, using mock service")
    FalkorDBClient = None
    FALKORDB_AVAILABLE = False

class FalkorDBService:
    """FalkorDB service for graph database operations"""
    
    def __init__(self):
        self.db = None
        self.graph = None
        self.connected = False
        self.use_mock = not FALKORDB_AVAILABLE
        
    async def initialize(self):
        """Initialize FalkorDB connection"""
        if not FALKORDB_AVAILABLE:
            logger.info("FalkorDB not available, using mock mode")
            self.use_mock = True
            self.connected = False
            return
            
        try:
            # Connect to FalkorDB
            self.db = FalkorDBClient(
                host=settings.falkordb_host,
                port=settings.falkordb_port,
                password=settings.falkordb_password
            )
            
            # Select the knowledge graph
            self.graph = self.db.select_graph(settings.falkordb_graph_name)
            
            # Test connection (synchronous call)
            result = self._execute_query_sync("RETURN 1 as test")
            if result:
                self.connected = True
                logger.info("FalkorDB service initialized successfully")
            else:
                raise Exception("Connection test failed")
                
        except Exception as e:
            logger.error(f"Failed to initialize FalkorDB service: {e}")
            self.connected = False
            self.use_mock = True
    
    def _execute_query_sync(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a synchronous Cypher query on FalkorDB for initialization"""
        if self.use_mock:
            return {'result': 'mock'}
            
        try:
            if not self.graph:
                raise RuntimeError("FalkorDB graph not initialized")
            
            logger.debug(f"Executing sync query: {query}")
            result = self.graph.query(query, params or {})
            return result
        except Exception as e:
            logger.error(f"Sync query execution failed: {e}")
            raise
    
    async def close(self):
        """Close FalkorDB connection"""
        if self.db and not self.use_mock:
            try:
                self.db.close()
            except AttributeError:
                # FalkorDB client might not have close method
                pass
            self.connected = False
            logger.info("FalkorDB connection closed")
    
    async def _execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a Cypher query on FalkorDB"""
        if self.use_mock:
            # Return mock data based on query type
            if "CREATE" in query.upper():
                return {'result_set': [['mock-id']]}
            elif "MATCH" in query.upper() and "RETURN" in query.upper():
                return {'result_set': []}
            else:
                return {'result_set': []}
        
        try:
            if not self.connected or not self.graph:
                raise RuntimeError("FalkorDB service not initialized")
            
            logger.debug(f"Executing query: {query}")
            # FalkorDB query method is synchronous
            result = self.graph.query(query, params or {})
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def create_node(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Create a new node in the graph"""
        if self.use_mock:
            node_id = str(uuid.uuid4())
            logger.info(f"Mock created node: {node_id} of type {node_type}")
            return node_id
            
        try:
            node_id = str(uuid.uuid4())
            properties['id'] = node_id
            properties['created_at'] = datetime.utcnow().isoformat()
            
            # Build property string for Cypher query
            prop_strings = []
            for key, value in properties.items():
                if isinstance(value, str):
                    prop_strings.append(f"{key}: '{value}'")
                else:
                    prop_strings.append(f"{key}: {value}")
            
            prop_str = "{" + ", ".join(prop_strings) + "}"
            
            query = f"CREATE (n:{node_type} {prop_str}) RETURN n.id as id"
            result = await self._execute_query(query)
            
            if result and result.result_set:
                logger.info(f"Created node: {node_id} of type {node_type}")
                return node_id
            else:
                raise Exception("Node creation failed")
                
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            raise
    
    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID"""
        if self.use_mock:
            return None
            
        try:
            query = f"MATCH (n) WHERE n.id = '{node_id}' RETURN n"
            result = await self._execute_query(query)
            
            if result and result.result_set:
                node_data = result.result_set[0][0]
                return self._format_node(node_data)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}")
            raise
    
    async def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """Update a node's properties"""
        if self.use_mock:
            logger.info(f"Mock updated node: {node_id}")
            return True
            
        try:
            properties['updated_at'] = datetime.utcnow().isoformat()
            
            # Build SET clause
            set_clauses = []
            for key, value in properties.items():
                if isinstance(value, str):
                    set_clauses.append(f"n.{key} = '{value}'")
                else:
                    set_clauses.append(f"n.{key} = {value}")
            
            set_str = ", ".join(set_clauses)
            
            query = f"MATCH (n) WHERE n.id = '{node_id}' SET {set_str} RETURN n.id"
            result = await self._execute_query(query)
            
            if result and result.result_set:
                logger.info(f"Updated node: {node_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to update node {node_id}: {e}")
            raise
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships"""
        if self.use_mock:
            logger.info(f"Mock deleted node: {node_id}")
            return True
            
        try:
            query = f"MATCH (n) WHERE n.id = '{node_id}' DETACH DELETE n"
            result = await self._execute_query(query)
            
            logger.info(f"Deleted node: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete node {node_id}: {e}")
            raise
    
    async def search_nodes(self, query_text: str, node_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search nodes by text content"""
        if self.use_mock:
            # Return mock data for testing
            if query_text:
                return []  # No mock results for real queries
            else:
                return []  # No mock results
        
        try:
            # Build search query
            match_clause = "MATCH (n)"
            if node_type:
                match_clause = f"MATCH (n:{node_type})"
            
            # Simple text search in name and content properties
            where_clause = f"WHERE n.name CONTAINS '{query_text}' OR n.content CONTAINS '{query_text}'"
            
            if not query_text.strip():
                where_clause = ""  # Return all nodes if no query
            
            query = f"{match_clause} {where_clause} RETURN n LIMIT {limit}"
            result = await self._execute_query(query)
            
            nodes = []
            if result and result.result_set:
                for row in result.result_set:
                    node_data = self._format_node(row[0])
                    if node_data:
                        nodes.append(node_data)
            
            logger.info(f"Search returned {len(nodes)} nodes for query: {query_text}")
            return nodes
        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            raise
    
    async def create_relationship(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """Create a relationship between two nodes"""
        if self.use_mock:
            rel_id = str(uuid.uuid4())
            logger.info(f"Mock created relationship: {rel_id}")
            return rel_id
            
        try:
            rel_id = str(uuid.uuid4())
            rel_props = properties or {}
            rel_props['id'] = rel_id
            rel_props['created_at'] = datetime.utcnow().isoformat()
            
            # Build property string
            prop_strings = []
            for key, value in rel_props.items():
                if isinstance(value, str):
                    prop_strings.append(f"{key}: '{value}'")
                else:
                    prop_strings.append(f"{key}: {value}")
            
            prop_str = "{" + ", ".join(prop_strings) + "}" if prop_strings else ""
            
            query = f"""
            MATCH (a) WHERE a.id = '{source_id}'
            MATCH (b) WHERE b.id = '{target_id}'
            CREATE (a)-[r:{relation_type} {prop_str}]->(b)
            RETURN r.id as id
            """
            
            result = await self._execute_query(query)
            
            if result and result.result_set:
                logger.info(f"Created relationship: {rel_id}")
                return rel_id
            else:
                raise Exception("Relationship creation failed")
                
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise
    
    async def get_node_relationships(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a node"""
        if self.use_mock:
            return []
            
        try:
            query = f"""
            MATCH (n)-[r]-(m) 
            WHERE n.id = '{node_id}'
            RETURN r, startNode(r) as source, endNode(r) as target
            """
            
            result = await self._execute_query(query)
            
            relationships = []
            if result and result.result_set:
                for row in result.result_set:
                    rel_data = self._format_relationship(row[0], row[1], row[2])
                    if rel_data:
                        relationships.append(rel_data)
            
            return relationships
        except Exception as e:
            logger.error(f"Failed to get relationships for node {node_id}: {e}")
            raise
    
    async def get_graph_stats(self) -> Dict[str, int]:
        """Get graph statistics"""
        if self.use_mock:
            return {'nodes': 0, 'relationships': 0}
            
        try:
            # Count nodes
            nodes_result = await self._execute_query("MATCH (n) RETURN count(n) as count")
            node_count = nodes_result.result_set[0][0] if nodes_result and nodes_result.result_set else 0
            
            # Count relationships  
            rels_result = await self._execute_query("MATCH ()-[r]-() RETURN count(r) as count")
            rel_count = rels_result.result_set[0][0] if rels_result and rels_result.result_set else 0
            
            return {
                'nodes': node_count,
                'relationships': rel_count // 2  # Divide by 2 because relationships are counted twice
            }
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {'nodes': 0, 'relationships': 0}
    
    def _format_node(self, node_data: Any) -> Optional[Dict[str, Any]]:
        """Format node data from FalkorDB result"""
        if self.use_mock:
            return None
            
        try:
            if not node_data:
                return None
            
            # Extract properties from node
            properties = {}
            for key in node_data.properties:
                properties[key] = node_data.properties[key]
            
            return {
                'id': properties.get('id', ''),
                'name': properties.get('name', ''),
                'type': properties.get('type', ''),
                'content': properties.get('content', ''),
                'properties': {k: v for k, v in properties.items() 
                             if k not in ['id', 'name', 'type', 'content']},
                'created_at': properties.get('created_at', ''),
                'updated_at': properties.get('updated_at')
            }
        except Exception as e:
            logger.error(f"Failed to format node data: {e}")
            return None
    
    def _format_relationship(self, rel_data: Any, source_node: Any, target_node: Any) -> Optional[Dict[str, Any]]:
        """Format relationship data from FalkorDB result"""
        if self.use_mock:
            return None
            
        try:
            if not rel_data:
                return None
            
            properties = {}
            for key in rel_data.properties:
                properties[key] = rel_data.properties[key]
            
            return {
                'id': properties.get('id', ''),
                'source_id': source_node.properties.get('id', ''),
                'target_id': target_node.properties.get('id', ''),
                'relation_type': rel_data.relation,
                'description': properties.get('description'),
                'weight': properties.get('weight', 1.0),
                'properties': {k: v for k, v in properties.items() 
                             if k not in ['id', 'description', 'weight']},
                'created_at': properties.get('created_at', ''),
                'updated_at': properties.get('updated_at')
            }
        except Exception as e:
            logger.error(f"Failed to format relationship data: {e}")
            return None