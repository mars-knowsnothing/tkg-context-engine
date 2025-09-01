'use client';

import { useState, useEffect } from 'react';
import { Activity, Database, MessageCircle, Clock, TrendingUp } from 'lucide-react';
import { knowledgeApi, healthApi } from '@/lib/api';
import { KnowledgeNode } from '@/lib/types';
import { formatDate } from '@/lib/utils';

const Dashboard = () => {
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
  const [stats, setStats] = useState({
    totalNodes: 0,
    totalRelations: 0,
    recentActivity: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setLoading(true);
        
        // Load knowledge nodes
        const nodesResponse = await knowledgeApi.getAll();
        const nodesData = nodesResponse.data.slice(0, 5); // Limit to 5 nodes
        setNodes(nodesData);
        
        // Update stats
        setStats({
          totalNodes: nodesData.length,
          totalRelations: 0, // This would come from relations API
          recentActivity: nodesData.filter(node => {
            const nodeDate = new Date(node.created_at);
            const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
            return nodeDate > oneDayAgo;
          }).length
        });
        
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const StatCard = ({ 
    icon: Icon, 
    title, 
    value, 
    subtitle, 
    color = 'blue' 
  }: {
    icon: any;
    title: string;
    value: string | number;
    subtitle: string;
    color?: 'blue' | 'green' | 'purple' | 'orange';
  }) => {
    const colorClasses = {
      blue: 'from-blue-500 to-blue-600',
      green: 'from-green-500 to-green-600',
      purple: 'from-purple-500 to-purple-600',
      orange: 'from-orange-500 to-orange-600'
    };

    return (
      <div className="glass p-6 rounded-xl hover:glow transition-all duration-300">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-gray-400 text-sm font-medium mb-1">{title}</p>
            <p className="text-2xl font-bold text-white mb-1">{value}</p>
            <p className="text-xs text-gray-500">{subtitle}</p>
          </div>
          <div className={`w-12 h-12 rounded-lg bg-gradient-to-r ${colorClasses[color]} flex items-center justify-center`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
        </div>
      </div>
    );
  };

  const RecentNodeCard = ({ node }: { node: KnowledgeNode }) => (
    <div className="glass p-4 rounded-lg hover:bg-white/10 transition-all duration-200 border-l-2 border-blue-400">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h4 className="text-white font-medium text-sm mb-1">
            {node.name}
          </h4>
          <p className="text-gray-400 text-xs mb-2 line-clamp-2">
            {node.content}
          </p>
          <div className="flex items-center space-x-2">
            <span className={`
              px-2 py-1 rounded-full text-xs font-medium
              ${node.type === 'entity' ? 'bg-blue-500/20 text-blue-300' :
                node.type === 'event' ? 'bg-green-500/20 text-green-300' :
                'bg-purple-500/20 text-purple-300'}
            `}>
              {node.type}
            </span>
            <span className="text-gray-500 text-xs">
              {formatDate(node.created_at)}
            </span>
          </div>
        </div>
        <Database className="w-4 h-4 text-gray-400 flex-shrink-0 ml-2" />
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          <span className="text-gray-400">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 terminal-text">
            Knowledge Graph Dashboard
          </h1>
          <p className="text-gray-400">
            Overview of your time-aware knowledge graph system
          </p>
        </div>
        <div className="flex items-center space-x-2 glass px-4 py-2 rounded-lg">
          <Activity className="w-4 h-4 text-green-400" />
          <span className="text-sm text-gray-300">System Active</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={Database}
          title="Total Nodes"
          value={stats.totalNodes}
          subtitle="Knowledge entities"
          color="blue"
        />
        <StatCard
          icon={TrendingUp}
          title="Relations"
          value={stats.totalRelations}
          subtitle="Connected relationships"
          color="green"
        />
        <StatCard
          icon={Clock}
          title="Recent Activity"
          value={stats.recentActivity}
          subtitle="Last 24 hours"
          color="purple"
        />
        <StatCard
          icon={MessageCircle}
          title="Chat Sessions"
          value="--"
          subtitle="Interactive queries"
          color="orange"
        />
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Nodes */}
        <div className="glass p-6 rounded-xl">
          <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
            <Database className="w-5 h-5 mr-2 text-blue-400" />
            Recent Knowledge Nodes
          </h3>
          <div className="space-y-3">
            {nodes.length > 0 ? (
              nodes.map((node) => (
                <RecentNodeCard key={node.id} node={node} />
              ))
            ) : (
              <div className="text-center py-8">
                <Database className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                <p className="text-gray-400">No knowledge nodes yet</p>
                <p className="text-gray-500 text-sm">
                  Create your first knowledge node to get started
                </p>
              </div>
            )}
          </div>
        </div>

        {/* System Status */}
        <div className="glass p-6 rounded-xl">
          <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-green-400" />
            System Status
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-green-500/10 rounded-lg border border-green-500/20">
              <div className="flex items-center space-x-3">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-white font-medium">API Server</span>
              </div>
              <span className="text-green-400 text-sm">Online</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-green-500/10 rounded-lg border border-green-500/20">
              <div className="flex items-center space-x-3">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-white font-medium">Graphiti Engine</span>
              </div>
              <span className="text-green-400 text-sm">Mock Mode</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
              <div className="flex items-center space-x-3">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                <span className="text-white font-medium">Frontend</span>
              </div>
              <span className="text-blue-400 text-sm">Connected</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;