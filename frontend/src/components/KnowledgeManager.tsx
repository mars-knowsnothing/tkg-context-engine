'use client';

import { useState, useEffect } from 'react';
import { Plus, Search, Database, Edit3, Trash2, Eye, Filter } from 'lucide-react';
import { knowledgeApi } from '@/lib/api';
import { KnowledgeNode, KnowledgeNodeCreate, NodeType } from '@/lib/types';
import { formatDate, truncateText, debounce } from '@/lib/utils';
import { cn } from '@/lib/utils';

const KnowledgeManager = () => {
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
  const [filteredNodes, setFilteredNodes] = useState<KnowledgeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<NodeType | 'all'>('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingNode, setEditingNode] = useState<KnowledgeNode | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);

  // Form state
  const [formData, setFormData] = useState<KnowledgeNodeCreate>({
    name: '',
    type: NodeType.ENTITY,
    content: '',
    properties: {}
  });

  useEffect(() => {
    loadNodes();
  }, []);

  useEffect(() => {
    // Filter nodes based on search query and type
    let filtered = nodes;
    
    if (searchQuery) {
      filtered = filtered.filter(node =>
        node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        node.content.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    if (selectedType !== 'all') {
      filtered = filtered.filter(node => node.type === selectedType);
    }
    
    setFilteredNodes(filtered);
  }, [nodes, searchQuery, selectedType]);

  const loadNodes = async () => {
    try {
      setLoading(true);
      const data = await knowledgeApi.list();
      setNodes(data);
    } catch (error) {
      console.error('Failed to load nodes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNode = async () => {
    try {
      const newNode = await knowledgeApi.create(formData);
      setNodes([newNode, ...nodes]);
      setShowCreateForm(false);
      setFormData({
        name: '',
        type: NodeType.ENTITY,
        content: '',
        properties: {}
      });
    } catch (error) {
      console.error('Failed to create node:', error);
    }
  };

  const handleDeleteNode = async (id: string) => {
    if (!confirm('Are you sure you want to delete this node?')) return;
    
    try {
      await knowledgeApi.delete(id);
      setNodes(nodes.filter(node => node.id !== id));
      if (selectedNode?.id === id) {
        setSelectedNode(null);
      }
    } catch (error) {
      console.error('Failed to delete node:', error);
    }
  };

  const debouncedSearch = debounce((query: string) => {
    setSearchQuery(query);
  }, 300);

  const NodeCard = ({ node }: { node: KnowledgeNode }) => (
    <div className="glass p-4 rounded-lg hover:glow transition-all duration-200 cursor-pointer"
         onClick={() => setSelectedNode(node)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-white font-medium">{node.name}</h3>
            <span className={cn(
              "px-2 py-1 rounded-full text-xs font-medium",
              node.type === 'entity' ? 'bg-blue-500/20 text-blue-300' :
              node.type === 'event' ? 'bg-green-500/20 text-green-300' :
              'bg-purple-500/20 text-purple-300'
            )}>
              {node.type}
            </span>
          </div>
          <p className="text-gray-400 text-sm mb-3 line-clamp-2">
            {truncateText(node.content, 120)}
          </p>
          <div className="flex items-center justify-between">
            <span className="text-gray-500 text-xs">
              {formatDate(node.created_at)}
            </span>
            <div className="flex space-x-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedNode(node);
                }}
                className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white"
                title="View details"
              >
                <Eye className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingNode(node);
                  setFormData({
                    name: node.name,
                    type: node.type,
                    content: node.content,
                    properties: node.properties
                  });
                }}
                className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white"
                title="Edit"
              >
                <Edit3 className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteNode(node.id);
                }}
                className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-red-400"
                title="Delete"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const CreateNodeForm = () => (
    <div className="glass p-6 rounded-xl">
      <h3 className="text-xl font-semibold text-white mb-4">
        {editingNode ? 'Edit Node' : 'Create New Node'}
      </h3>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Name
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({...formData, name: e.target.value})}
            className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            placeholder="Enter node name..."
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Type
          </label>
          <select
            value={formData.type}
            onChange={(e) => setFormData({...formData, type: e.target.value as NodeType})}
            className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-400/50"
          >
            <option value={NodeType.ENTITY}>Entity</option>
            <option value={NodeType.EVENT}>Event</option>
            <option value={NodeType.CONCEPT}>Concept</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Content
          </label>
          <textarea
            value={formData.content}
            onChange={(e) => setFormData({...formData, content: e.target.value})}
            rows={4}
            className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            placeholder="Enter node content/description..."
          />
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={handleCreateNode}
            className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded-lg transition-colors duration-200"
          >
            {editingNode ? 'Update Node' : 'Create Node'}
          </button>
          <button
            onClick={() => {
              setShowCreateForm(false);
              setEditingNode(null);
              setFormData({
                name: '',
                type: NodeType.ENTITY,
                content: '',
                properties: {}
              });
            }}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors duration-200"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  const NodeDetails = ({ node }: { node: KnowledgeNode }) => (
    <div className="glass p-6 rounded-xl">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-2xl font-semibold text-white mb-2">{node.name}</h3>
          <span className={cn(
            "px-3 py-1 rounded-full text-sm font-medium",
            node.type === 'entity' ? 'bg-blue-500/20 text-blue-300' :
            node.type === 'event' ? 'bg-green-500/20 text-green-300' :
            'bg-purple-500/20 text-purple-300'
          )}>
            {node.type}
          </span>
        </div>
        <button
          onClick={() => setSelectedNode(null)}
          className="text-gray-400 hover:text-white"
        >
          ×
        </button>
      </div>
      
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-2">Content</h4>
          <p className="text-gray-200 leading-relaxed">{node.content}</p>
        </div>
        
        <div>
          <h4 className="text-sm font-medium text-gray-300 mb-2">Metadata</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Created:</span>
              <span className="text-gray-200">{formatDate(node.created_at)}</span>
            </div>
            {node.updated_at && (
              <div className="flex justify-between">
                <span className="text-gray-400">Updated:</span>
                <span className="text-gray-200">{formatDate(node.updated_at)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-400">ID:</span>
              <span className="text-gray-200 font-mono text-xs">{node.id}</span>
            </div>
          </div>
        </div>
        
        {Object.keys(node.properties).length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-300 mb-2">Properties</h4>
            <pre className="text-xs bg-black/20 p-3 rounded border border-white/10 text-gray-300 overflow-x-auto">
              {JSON.stringify(node.properties, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 terminal-text">
            Knowledge Management
          </h1>
          <p className="text-gray-400">
            Manage your knowledge graph nodes and relationships
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center space-x-2 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors duration-200 glow"
        >
          <Plus className="w-5 h-5" />
          <span>Add Node</span>
        </button>
      </div>

      {/* Filters */}
      <div className="glass p-4 rounded-xl">
        <div className="flex flex-col md:flex-row space-y-4 md:space-y-0 md:space-x-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              onChange={(e) => debouncedSearch(e.target.value)}
              placeholder="Search nodes..."
              className="w-full pl-10 pr-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            />
          </div>
          
          {/* Type Filter */}
          <div className="flex items-center space-x-2">
            <Filter className="w-5 h-5 text-gray-400" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value as NodeType | 'all')}
              className="px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            >
              <option value="all">All Types</option>
              <option value={NodeType.ENTITY}>Entities</option>
              <option value={NodeType.EVENT}>Events</option>
              <option value={NodeType.CONCEPT}>Concepts</option>
            </select>
          </div>
        </div>
      </div>

      {/* Create/Edit Form */}
      {(showCreateForm || editingNode) && <CreateNodeForm />}

      {/* Node Details */}
      {selectedNode && <NodeDetails node={selectedNode} />}

      {/* Nodes Grid */}
      <div className="glass p-6 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-white flex items-center">
            <Database className="w-5 h-5 mr-2 text-blue-400" />
            Knowledge Nodes ({filteredNodes.length})
          </h3>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center space-x-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
              <span className="text-gray-400">Loading nodes...</span>
            </div>
          </div>
        ) : filteredNodes.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredNodes.map((node) => (
              <NodeCard key={node.id} node={node} />
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Database className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 text-lg mb-2">No nodes found</p>
            <p className="text-gray-500">
              {searchQuery || selectedType !== 'all'
                ? 'Try adjusting your filters'
                : 'Create your first knowledge node to get started'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeManager;