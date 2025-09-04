'use client';

import { useState, useCallback, useEffect } from 'react';
import { Clock, Calendar, Filter, Search, Database, Activity, AlertCircle, CheckCircle, Clock3, XCircle, Target, Brain, Zap, CircleDot, GitBranch } from 'lucide-react';
import { TemporalQueryRequest, TemporalQueryResult, TemporalValidityState, KnowledgeNode, TimeInterval } from '@/lib/types';
import { formatDate, cn } from '@/lib/utils';
import axios from 'axios';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

const TemporalExplorer = () => {
  const [queryResult, setQueryResult] = useState<TemporalQueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [validityStats, setValidityStats] = useState<any>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  
  // Query form state
  const [query, setQuery] = useState('');
  const [atTime, setAtTime] = useState('');
  const [validityFilter, setValidityFilter] = useState<TemporalValidityState | ''>('');

  const executeTemporalQuery = useCallback(async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    try {
      const request: TemporalQueryRequest = {
        query: query.trim(),
        limit: 20,
      };
      
      if (atTime) {
        request.at_time = new Date(atTime).toISOString();
      }
      
      if (validityFilter) {
        request.validity_filter = validityFilter;
      }
      
      const response = await axios.post(`${BASE_URL}/api/temporal/query`, request);
      setQueryResult(response.data);
    } catch (error) {
      console.error('Temporal query failed:', error);
    } finally {
      setLoading(false);
    }
  }, [query, atTime, validityFilter]);

  const loadValidityStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const response = await axios.get(`${BASE_URL}/api/temporal/validity-states`);
      setValidityStats(response.data);
    } catch (error) {
      console.error('Failed to load validity stats:', error);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const createDemoData = useCallback(async () => {
    try {
      await axios.get(`${BASE_URL}/api/temporal/demo/create-temporal-data`);
      await loadValidityStats(); // Refresh stats
    } catch (error) {
      console.error('Failed to create demo data:', error);
    }
  }, [loadValidityStats]);

  // Initialize component
  useEffect(() => {
    loadValidityStats();
  }, [loadValidityStats]);

  const getValidityIcon = (state: TemporalValidityState) => {
    switch (state) {
      case 'valid':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'pending':
        return <Clock3 className="w-4 h-4 text-yellow-400" />;
      case 'expired':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getValidityColor = (state: TemporalValidityState) => {
    switch (state) {
      case 'valid':
        return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'pending':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
      case 'expired':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      default:
        return 'bg-gray-500/20 text-gray-300 border-gray-500/30';
    }
  };

  // 判断事件是否为客观事实事件
  const isFactualEvent = (node: KnowledgeNode): boolean => {
    const factualSources = ['运维监控', 'APM', '故障管理系统', 'K8s', 'SystemObserver'];
    const factualTypes = ['Observation', 'Service', 'FaultEvent', 'K8sEvent', 'Alert'];
    const inferredTypes = ['InferredEvent', 'AnalysisResult', 'PredictionEvent', 'RootCauseEvent'];
    
    const source = node.properties?.source;
    const originalType = node.properties?.original_type;
    const name = (node.name || '').toLowerCase();
    const content = (node.content || '').toLowerCase();
    
    // 如果是明确的推理事件类型，返回false
    if (originalType && inferredTypes.includes(originalType)) {
      return false;
    }
    
    // 如果名称或内容包含推理关键词，返回false  
    const inferredKeywords = ['分析', '推理', '预测', '建议', '根因', '自动修复', '容量规划', '异常检测'];
    if (inferredKeywords.some(keyword => name.includes(keyword) || content.includes(keyword))) {
      return false;
    }
    
    // 如果来源是监控系统或明确的事实类型，返回true
    if ((source && factualSources.includes(source)) || 
        (originalType && factualTypes.includes(originalType))) {
      return true;
    }
    
    // 默认为客观事实事件（监控数据等）
    return true;
  };

  // 获取事件时间戳用于排序
  const getEventTimestamp = (node: KnowledgeNode): Date => {
    // 优先使用事件发生时间
    if (node.properties?.time) {
      return new Date(node.properties.time);
    }
    // 其次使用有效时间开始时间
    if (node.valid_time?.start_time) {
      return new Date(node.valid_time.start_time);
    }
    // 最后使用创建时间
    return new Date(node.created_at);
  };

  // 时间线事件组件
  const TimelineEventCard = ({ node, isLeft }: { node: KnowledgeNode; isLeft: boolean }) => {
    const isFactual = isFactualEvent(node);
    const timestamp = getEventTimestamp(node);
    
    return (
      <div className="flex items-start relative">
        {/* 左侧事件区域 */}
        <div className={cn("w-2/5", isLeft ? "flex justify-end pr-4" : "")}>
          {isLeft && (
            <div className="glass p-3 rounded-lg hover:glow transition-all duration-200 border-l-3 border-l-blue-400 bg-blue-500/8 max-w-xs w-full">
              {/* 事件头部 */}
              <div className="flex items-start space-x-2">
                <Target className="w-3 h-3 text-blue-400 flex-shrink-0 mt-1" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <h4 className="text-white font-medium text-sm truncate">{node.name}</h4>
                    {node.validity_state && (
                      <div className={cn(
                        "flex items-center space-x-1 px-1.5 py-0.5 rounded-full text-xs border flex-shrink-0",
                        getValidityColor(node.validity_state)
                      )}>
                        {getValidityIcon(node.validity_state)}
                        <span className="capitalize">{node.validity_state}</span>
                      </div>
                    )}
                  </div>
                  
                  {/* 时间戳 */}
                  <div className="flex items-center space-x-1 text-xs text-gray-400 mb-2">
                    <Clock className="w-3 h-3 flex-shrink-0" />
                    <span className="truncate">{formatDate(timestamp.toISOString())}</span>
                    {node.properties?.severity && (
                      <span className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0",
                        node.properties.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-300' :
                        node.properties.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-300' :
                        node.properties.severity === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-300' :
                        'bg-green-500/20 text-green-300'
                      )}>
                        {node.properties.severity}
                      </span>
                    )}
                  </div>
                  
                  <p className="text-gray-300 text-xs mb-2 line-clamp-2">
                    {node.content}
                  </p>
                  
                  {/* 事件来源 */}
                  <div className="flex flex-wrap gap-1">
                    {node.properties?.source && (
                      <span className="bg-white/5 px-1.5 py-0.5 rounded text-xs text-gray-500 truncate">
                        {node.properties.source}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* 中央时间线连接点和时间标签 */}
        <div className="w-1/5 flex flex-col items-center px-2">
          <div className="relative z-10 flex flex-col items-center">
            {/* 时间标签 */}
            <div className="bg-gray-800/80 px-2 py-1 rounded text-xs text-gray-300 mb-2 text-center border border-white/10">
              <div className="font-medium">
                {timestamp.toLocaleTimeString('zh-CN', { 
                  hour: '2-digit', 
                  minute: '2-digit',
                  second: '2-digit'
                })}
              </div>
              <div className="text-gray-500 text-xs">
                {timestamp.toLocaleDateString('zh-CN', { 
                  month: '2-digit', 
                  day: '2-digit' 
                })}
              </div>
            </div>
            
            {/* 连接点 */}
            <div className={cn(
              "w-4 h-4 rounded-full border-2 bg-gray-900 shadow-lg",
              isFactual ? "border-blue-400" : "border-purple-400"
            )}>
              <div className={cn(
                "w-2 h-2 rounded-full m-0.5",
                isFactual ? "bg-blue-400" : "bg-purple-400"
              )}></div>
            </div>
          </div>
        </div>
        
        {/* 右侧事件区域 */}
        <div className={cn("w-2/5", !isLeft ? "flex justify-start pl-4" : "")}>
          {!isLeft && (
            <div className="glass p-3 rounded-lg hover:glow transition-all duration-200 border-l-3 border-l-purple-400 bg-purple-500/8 max-w-xs w-full">
              {/* 事件头部 */}
              <div className="flex items-start space-x-2">
                <Brain className="w-3 h-3 text-purple-400 flex-shrink-0 mt-1" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <h4 className="text-white font-medium text-sm truncate">{node.name}</h4>
                    {node.validity_state && (
                      <div className={cn(
                        "flex items-center space-x-1 px-1.5 py-0.5 rounded-full text-xs border flex-shrink-0",
                        getValidityColor(node.validity_state)
                      )}>
                        {getValidityIcon(node.validity_state)}
                        <span className="capitalize">{node.validity_state}</span>
                      </div>
                    )}
                  </div>
                  
                  {/* 时间戳 */}
                  <div className="flex items-center space-x-1 text-xs text-gray-400 mb-2">
                    <Clock className="w-3 h-3 flex-shrink-0" />
                    <span className="truncate">{formatDate(timestamp.toISOString())}</span>
                    {node.properties?.severity && (
                      <span className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0",
                        node.properties.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-300' :
                        node.properties.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-300' :
                        node.properties.severity === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-300' :
                        'bg-green-500/20 text-green-300'
                      )}>
                        {node.properties.severity}
                      </span>
                    )}
                  </div>
                  
                  <p className="text-gray-300 text-xs mb-2 line-clamp-2">
                    {node.content}
                  </p>
                  
                  {/* 事件来源 */}
                  <div className="flex flex-wrap gap-1">
                    {node.properties?.source && (
                      <span className="bg-white/5 px-1.5 py-0.5 rounded text-xs text-gray-500 truncate">
                        {node.properties.source}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 terminal-text">
            Temporal Knowledge Explorer
          </h1>
          <p className="text-gray-400">
            Explore your knowledge graph across time with validity states and temporal queries
          </p>
        </div>
        <button
          onClick={createDemoData}
          className="flex items-center space-x-2 bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-lg transition-colors duration-200 glow"
        >
          <Clock className="w-5 h-5" />
          <span>Create Demo Data</span>
        </button>
      </div>

      {/* Validity Statistics */}
      <div className="glass p-6 rounded-xl">
        <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Activity className="w-5 h-5 mr-2 text-green-400" />
          Temporal Validity Overview
        </h3>
        {statsLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center space-x-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
              <span className="text-gray-400">Loading validity stats...</span>
            </div>
          </div>
        ) : validityStats ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              {Object.entries(validityStats.validity_breakdown || {}).map(([state, count]) => (
                <div key={state} className="text-center">
                  <div className={cn(
                    "w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-2 border-2",
                    getValidityColor(state as TemporalValidityState)
                  )}>
                    {getValidityIcon(state as TemporalValidityState)}
                  </div>
                  <div className="text-2xl font-bold text-white">{count as number}</div>
                  <div className="text-sm text-gray-400 capitalize">{state}</div>
                </div>
              ))}
            </div>
            <div className="text-center text-sm text-gray-400">
              Total Nodes: {validityStats.total_nodes} • Last Updated: {formatDate(validityStats.query_time)}
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-gray-400">
            Failed to load validity statistics
          </div>
        )}
      </div>

      {/* Temporal Query Interface */}
      <div className="glass p-6 rounded-xl">
        <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Search className="w-5 h-5 mr-2 text-blue-400" />
          Temporal Query
        </h3>
        
        <div className="space-y-4">
          {/* Query Input */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Query
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your temporal query (e.g., 'employees', 'projects')"
              className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            />
          </div>

          {/* Temporal Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Point in Time
              </label>
              <input
                type="datetime-local"
                value={atTime}
                onChange={(e) => setAtTime(e.target.value)}
                className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-400/50"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Validity Filter
              </label>
              <select
                value={validityFilter}
                onChange={(e) => setValidityFilter(e.target.value as TemporalValidityState | '')}
                className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-400/50"
              >
                <option value="">All States</option>
                <option value="valid">Valid Only</option>
                <option value="pending">Pending Only</option>
                <option value="expired">Expired Only</option>
                <option value="invalid">Invalid Only</option>
              </select>
            </div>
          </div>

          {/* Execute Button */}
          <button
            onClick={executeTemporalQuery}
            disabled={!query.trim() || loading}
            className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-not-allowed text-white py-3 px-6 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            ) : (
              <Search className="w-5 h-5" />
            )}
            <span>{loading ? 'Querying...' : 'Execute Temporal Query'}</span>
          </button>
        </div>
      </div>

      {/* Demo Queries */}
      <div className="glass p-6 rounded-xl">
        <h3 className="text-xl font-semibold text-white mb-4">
          Try These Temporal Queries
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { query: '故障', filter: '', desc: '查看故障事件时间线' },
            { query: 'APM', filter: 'valid', desc: '当前有效的APM监控数据' },
            { query: 'ittzp-auth-service', filter: '', desc: '认证服务相关事件' },
            { query: '监控', filter: 'valid', desc: '活跃监控事件' },
          ].map((example, index) => (
            <button
              key={index}
              onClick={() => {
                setQuery(example.query);
                setValidityFilter(example.filter as TemporalValidityState);
              }}
              className="text-left p-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors duration-200"
            >
              <div className="text-white font-medium">{example.query}</div>
              <div className="text-gray-400 text-sm">{example.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Query Results - Timeline View */}
      {queryResult && (
        <div className="glass p-6 rounded-xl">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white flex items-center">
              <GitBranch className="w-5 h-5 mr-2 text-green-400" />
              Temporal Timeline ({queryResult.nodes.length})
            </h3>
            <div className="text-sm text-gray-400">
              {queryResult.temporal_scope}
            </div>
          </div>

          {/* Timeline Legend */}
          <div className="mb-6 p-4 bg-gray-800/50 border border-white/10 rounded-lg">
            <h4 className="text-white font-medium mb-3">Timeline Legend</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2">
                  <Target className="w-4 h-4 text-blue-400" />
                  <div className="w-3 h-3 rounded-full border-2 border-blue-400 bg-blue-400"></div>
                </div>
                <div>
                  <div className="text-blue-300 font-medium text-sm">客观事实事件 (左侧)</div>
                  <div className="text-gray-400 text-xs">监控数据、系统日志、故障报告等直接观测到的事件</div>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <div className="flex items-center space-x-2">
                  <Brain className="w-4 h-4 text-purple-400" />
                  <div className="w-3 h-3 rounded-full border-2 border-purple-400 bg-purple-400"></div>
                </div>
                <div>
                  <div className="text-purple-300 font-medium text-sm">推理派生事件 (右侧)</div>
                  <div className="text-gray-400 text-xs">根因分析、预测结果、推理结论等分析得出的事件</div>
                </div>
              </div>
            </div>
          </div>

          {/* Results Summary */}
          <div className="mb-6 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
            <p className="text-blue-200 text-sm mb-2">{queryResult.explanation}</p>
            {queryResult.validity_summary && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(queryResult.validity_summary).map(([state, count]) => (
                  count > 0 && (
                    <span key={state} className={cn(
                      "px-2 py-1 rounded text-xs",
                      getValidityColor(state as TemporalValidityState)
                    )}>
                      {state}: {count}
                    </span>
                  )
                ))}
              </div>
            )}
          </div>

          {/* Timeline Container */}
          {queryResult.nodes.length > 0 ? (
            <div className="relative min-h-96 max-w-4xl mx-auto">
              {/* 中央时间线 */}
              <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-400 via-purple-400 to-green-400 rounded-full opacity-40 transform -translate-x-0.5">
                {/* 时间线装饰点 */}
                <div className="absolute top-0 left-1/2 w-2 h-2 bg-blue-400 rounded-full transform -translate-x-1/2 -translate-y-1"></div>
                <div className="absolute bottom-0 left-1/2 w-2 h-2 bg-green-400 rounded-full transform -translate-x-1/2 translate-y-1"></div>
              </div>
              
              {/* 排序后的事件节点 */}
              <div className="relative space-y-4 py-6">
                {queryResult.nodes
                  .sort((a, b) => getEventTimestamp(b).getTime() - getEventTimestamp(a).getTime())
                  .map((node, index) => {
                    const isFactual = isFactualEvent(node);
                    const isLast = index === queryResult.nodes.length - 1;
                    return (
                      <div key={node.id} className="relative">
                        <TimelineEventCard 
                          node={node} 
                          isLeft={isFactual} 
                        />
                        {/* 连接到下一个事件的线 */}
                        {!isLast && (
                          <div className="absolute left-1/2 bottom-0 w-0.5 h-4 bg-gray-400 opacity-20 transform -translate-x-0.5"></div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">No temporal events found</p>
              <p className="text-sm">Try adjusting your query or time range</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TemporalExplorer;