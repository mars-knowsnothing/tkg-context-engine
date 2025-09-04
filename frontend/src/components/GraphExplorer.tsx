'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, RefreshCw, Settings, ZoomIn, ZoomOut, Move } from 'lucide-react';

interface GraphNode {
  id: string;
  label: string;
  type: 'managed_object' | 'service' | 'event' | 'dependency';
  properties: any;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const GraphExplorer: React.FC = () => {
  const [managedObject, setManagedObject] = useState('');
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // 节点类型颜色配置
  const nodeColors = {
    managed_object: '#3B82F6', // 蓝色 - 受管对象
    service: '#10B981',        // 绿色 - 服务
    event: '#F59E0B',         // 橙色 - 事件
    dependency: '#8B5CF6'      // 紫色 - 依赖
  };

  // 查询受管对象相关数据
  const queryManagedObject = async () => {
    if (!managedObject.trim()) return;

    setLoading(true);
    try {
      // 模拟API调用，实际应该调用后端API
      const response = await fetch('/api/graph/managed-object', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          managed_object: managedObject,
          depth: 2 // 查询深度
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setGraphData(generateGraphData(managedObject, data));
      } else {
        // 如果API不存在，使用模拟数据
        setGraphData(generateMockGraphData(managedObject));
      }
    } catch (error) {
      console.log('使用模拟数据');
      setGraphData(generateMockGraphData(managedObject));
    } finally {
      setLoading(false);
    }
  };

  // 生成模拟图数据
  const generateMockGraphData = (centerObject: string): GraphData => {
    const nodes: GraphNode[] = [
      // 中心受管对象
      {
        id: centerObject,
        label: centerObject,
        type: 'managed_object',
        properties: {
          status: 'healthy',
          region: 'us-west-2',
          environment: 'production'
        }
      },
      // 相关服务
      {
        id: `${centerObject}-api`,
        label: `${centerObject} API`,
        type: 'service',
        properties: {
          status: 'running',
          port: 8080,
          health: 'healthy'
        }
      },
      {
        id: `${centerObject}-db`,
        label: `${centerObject} Database`,
        type: 'service',
        properties: {
          status: 'running',
          type: 'postgresql',
          health: 'healthy'
        }
      },
      {
        id: `${centerObject}-cache`,
        label: `${centerObject} Cache`,
        type: 'service',
        properties: {
          status: 'running',
          type: 'redis',
          health: 'healthy'
        }
      },
      // 相关事件
      {
        id: 'evt-001',
        label: 'CPU使用率告警',
        type: 'event',
        properties: {
          severity: 'warning',
          timestamp: new Date().toISOString(),
          metric: 'cpu_usage > 80%'
        }
      },
      {
        id: 'evt-002',
        label: '响应时间异常',
        type: 'event',
        properties: {
          severity: 'critical',
          timestamp: new Date().toISOString(),
          metric: 'response_time > 2s'
        }
      },
      // 依赖关系
      {
        id: 'dep-001',
        label: 'External API',
        type: 'dependency',
        properties: {
          type: 'external',
          endpoint: 'https://api.external.com'
        }
      }
    ];

    const edges: GraphEdge[] = [
      // 服务关系
      {
        id: 'edge-1',
        source: centerObject,
        target: `${centerObject}-api`,
        type: 'MANAGES',
        label: 'manages'
      },
      {
        id: 'edge-2',
        source: centerObject,
        target: `${centerObject}-db`,
        type: 'MANAGES',
        label: 'manages'
      },
      {
        id: 'edge-3',
        source: centerObject,
        target: `${centerObject}-cache`,
        type: 'MANAGES',
        label: 'manages'
      },
      // 事件关系
      {
        id: 'edge-4',
        source: 'evt-001',
        target: centerObject,
        type: 'AFFECTS',
        label: 'affects'
      },
      {
        id: 'edge-5',
        source: 'evt-002',
        target: `${centerObject}-api`,
        type: 'AFFECTS',
        label: 'affects'
      },
      // 依赖关系
      {
        id: 'edge-6',
        source: `${centerObject}-api`,
        target: 'dep-001',
        type: 'DEPENDS_ON',
        label: 'depends on'
      }
    ];

    return { nodes, edges };
  };

  // 生成真实图数据
  const generateGraphData = (centerObject: string, apiData: any): GraphData => {
    // 处理API返回的数据，转换为图数据格式
    return generateMockGraphData(centerObject); // 暂时使用模拟数据
  };

  // 力导向布局算法
  const applyForceLayout = (data: GraphData): GraphData => {
    const nodes = [...data.nodes];
    const edges = data.edges;
    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // 初始化节点位置
    nodes.forEach((node, index) => {
      if (node.type === 'managed_object') {
        node.x = centerX;
        node.y = centerY;
      } else {
        const angle = (index / nodes.length) * 2 * Math.PI;
        const radius = node.type === 'service' ? 150 : 
                      node.type === 'event' ? 100 : 200;
        node.x = centerX + Math.cos(angle) * radius;
        node.y = centerY + Math.sin(angle) * radius;
      }
    });

    // 简化的力导向算法
    for (let i = 0; i < 100; i++) {
      // 排斥力
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x! - nodes[i].x!;
          const dy = nodes[j].y! - nodes[i].y!;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance > 0) {
            const force = 1000 / (distance * distance);
            const fx = (dx / distance) * force;
            const fy = (dy / distance) * force;
            nodes[i].x! -= fx;
            nodes[i].y! -= fy;
            nodes[j].x! += fx;
            nodes[j].y! += fy;
          }
        }
      }

      // 吸引力（基于边）
      edges.forEach(edge => {
        const source = nodes.find(n => n.id === edge.source);
        const target = nodes.find(n => n.id === edge.target);
        if (source && target) {
          const dx = target.x! - source.x!;
          const dy = target.y! - source.y!;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance > 0) {
            const force = distance * 0.01;
            const fx = (dx / distance) * force;
            const fy = (dy / distance) * force;
            source.x! += fx;
            source.y! += fy;
            target.x! -= fx;
            target.y! -= fy;
          }
        }
      });

      // 保持中心节点位置
      const centerNode = nodes.find(n => n.type === 'managed_object');
      if (centerNode) {
        centerNode.x = centerX;
        centerNode.y = centerY;
      }
    }

    return { nodes, edges };
  };

  // 绘制图形
  const drawGraph = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 应用变换
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // 绘制背景网格
    drawGrid(ctx, canvas.width, canvas.height);

    // 绘制边
    graphData.edges.forEach(edge => {
      const source = graphData.nodes.find(n => n.id === edge.source);
      const target = graphData.nodes.find(n => n.id === edge.target);
      if (source && target) {
        drawEdge(ctx, source, target, edge);
      }
    });

    // 绘制节点
    graphData.nodes.forEach(node => {
      drawNode(ctx, node, selectedNode?.id === node.id);
    });

    ctx.restore();
  };

  // 绘制网格背景
  const drawGrid = (ctx: CanvasRenderingContext2D, width: number, height: number) => {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;

    const gridSize = 50;
    for (let x = 0; x <= width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    for (let y = 0; y <= height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  };

  // 绘制节点
  const drawNode = (ctx: CanvasRenderingContext2D, node: GraphNode, isSelected: boolean) => {
    const x = node.x || 0;
    const y = node.y || 0;
    const radius = node.type === 'managed_object' ? 30 : 20;

    // 绘制选中状态的光晕
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(x, y, radius + 8, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(59, 130, 246, 0.3)';
      ctx.fill();
    }

    // 绘制节点圆圈
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = nodeColors[node.type];
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 绘制节点标签
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(node.label, x, y + radius + 15);
  };

  // 绘制边
  const drawEdge = (ctx: CanvasRenderingContext2D, source: GraphNode, target: GraphNode, edge: GraphEdge) => {
    const sx = source.x || 0;
    const sy = source.y || 0;
    const tx = target.x || 0;
    const ty = target.y || 0;

    // 绘制边线
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(tx, ty);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 绘制箭头
    const angle = Math.atan2(ty - sy, tx - sx);
    const arrowLength = 10;
    const arrowAngle = Math.PI / 6;

    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(
      tx - arrowLength * Math.cos(angle - arrowAngle),
      ty - arrowLength * Math.sin(angle - arrowAngle)
    );
    ctx.moveTo(tx, ty);
    ctx.lineTo(
      tx - arrowLength * Math.cos(angle + arrowAngle),
      ty - arrowLength * Math.sin(angle + arrowAngle)
    );
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 绘制边标签
    const midX = (sx + tx) / 2;
    const midY = (sy + ty) / 2;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(edge.label || edge.type, midX, midY - 5);
  };

  // 处理鼠标事件
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;

    // 检查是否点击了节点
    const clickedNode = graphData.nodes.find(node => {
      const dx = x - (node.x || 0);
      const dy = y - (node.y || 0);
      const radius = node.type === 'managed_object' ? 30 : 20;
      return Math.sqrt(dx * dx + dy * dy) <= radius;
    });

    if (clickedNode) {
      setSelectedNode(clickedNode);
    } else {
      setSelectedNode(null);
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.1, Math.min(3, prev * delta)));
  };

  // 重置视图
  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // 更新图形数据并应用布局
  useEffect(() => {
    if (graphData.nodes.length > 0) {
      const layoutData = applyForceLayout(graphData);
      setGraphData(layoutData);
    }
  }, [graphData.nodes.length]);

  // 绘制图形
  useEffect(() => {
    drawGraph();
  }, [graphData, zoom, pan, selectedNode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* 头部控制栏 */}
      <div className="border-b border-white/10 backdrop-blur-sm bg-black/20 p-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              图形化数据探索器
            </h1>
            <div className="flex items-center gap-2 bg-black/30 rounded-lg p-2">
              <Search className="w-5 h-5 text-blue-400" />
              <input
                type="text"
                value={managedObject}
                onChange={(e) => setManagedObject(e.target.value)}
                placeholder="输入受管对象名称"
                className="bg-transparent text-white placeholder-white/60 border-none outline-none w-64"
                onKeyPress={(e) => e.key === 'Enter' && queryManagedObject()}
              />
              <button
                onClick={queryManagedObject}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white rounded-lg transition-colors flex items-center gap-2"
              >
                {loading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                查询
              </button>
            </div>
          </div>

          {/* 工具栏 */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoom(prev => Math.min(3, prev * 1.2))}
              className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
              title="放大"
            >
              <ZoomIn className="w-5 h-5 text-white" />
            </button>
            <button
              onClick={() => setZoom(prev => Math.max(0.1, prev / 1.2))}
              className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
              title="缩小"
            >
              <ZoomOut className="w-5 h-5 text-white" />
            </button>
            <button
              onClick={resetView}
              className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
              title="重置视图"
            >
              <Move className="w-5 h-5 text-white" />
            </button>
            <div className="text-white/60 text-sm px-2">
              {Math.round(zoom * 100)}%
            </div>
          </div>
        </div>
      </div>

      <div className="flex h-[calc(100vh-80px)]">
        {/* 主图形区域 */}
        <div className="flex-1 relative">
          <canvas
            ref={canvasRef}
            width={800}
            height={600}
            className="w-full h-full cursor-move"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onWheel={handleWheel}
            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
          />
          
          {/* 图例 */}
          <div className="absolute top-4 left-4 bg-black/40 backdrop-blur-sm rounded-lg p-4">
            <h3 className="text-white font-semibold mb-3">图例</h3>
            <div className="space-y-2">
              {Object.entries(nodeColors).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2">
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-white/80 text-sm">
                    {type === 'managed_object' ? '受管对象' :
                     type === 'service' ? '服务' :
                     type === 'event' ? '事件' : '依赖'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 加载状态 */}
          {loading && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <div className="bg-black/60 backdrop-blur-sm rounded-lg p-6 flex items-center gap-3">
                <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
                <span className="text-white">正在查询数据...</span>
              </div>
            </div>
          )}
        </div>

        {/* 右侧信息面板 */}
        {selectedNode && (
          <div className="w-80 bg-black/40 backdrop-blur-sm border-l border-white/10 p-4">
            <h3 className="text-white font-semibold text-lg mb-4">节点详情</h3>
            
            <div className="space-y-4">
              <div>
                <label className="text-white/60 text-sm">名称</label>
                <p className="text-white font-medium">{selectedNode.label}</p>
              </div>
              
              <div>
                <label className="text-white/60 text-sm">类型</label>
                <p className="text-white font-medium">
                  {selectedNode.type === 'managed_object' ? '受管对象' :
                   selectedNode.type === 'service' ? '服务' :
                   selectedNode.type === 'event' ? '事件' : '依赖'}
                </p>
              </div>

              <div>
                <label className="text-white/60 text-sm">属性</label>
                <div className="bg-black/30 rounded-lg p-3 mt-2">
                  <pre className="text-white/80 text-xs">
                    {JSON.stringify(selectedNode.properties, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphExplorer;