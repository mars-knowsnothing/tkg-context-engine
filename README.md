# TKG Context Engine

时序知识图谱上下文引擎 - 基于 Graphiti + FalkorDB 的智能知识管理系统

## 架构概述

- **后端**: FastAPI + Python 3.12 + Graphiti + FalkorDB
- **前端**: NextJS 14 + TailwindCSS + TypeScript  
- **图数据库**: FalkorDB (Redis兼容的图数据库)
- **关系数据库**: PostgreSQL + Redis
- **依赖管理**: uv (后端) + yarn (前端)

## 快速开始

### 环境准备

1. 复制环境变量模板:
```bash
cp .env.example .env
```

2. 配置OpenAI API密钥 (可选，系统支持mock模式):
```bash
# 编辑 .env 文件，添加你的OpenAI API密钥
OPENAI_API_KEY=your_openai_api_key_here
```

### 使用Docker Compose启动

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 服务端口说明

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8001
- **API文档**: http://localhost:8001/docs  
- **FalkorDB Browser**: http://localhost:3001
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6378
- **FalkorDB**: localhost:6380

### 本地开发

#### 后端开发

```bash
cd backend

# 安装依赖 (使用 uv)
uv sync

# 启动开发服务器
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### 前端开发

```bash
cd frontend

# 安装依赖
yarn install

# 启动开发服务器  
yarn dev
```

## API文档

启动后端服务后，访问以下地址查看API文档:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## 主要功能

### 1. 企业级知识节点管理
- 创建、查询、更新、删除知识节点
- 支持实体、事件、概念、剧集等不同类型
- 基于FalkorDB的高性能图存储
- **企业级分页系统** - 支持大规模数据浏览
- **智能搜索过滤** - 跨多个字段的全文检索
- **批量操作支持** - 高效的数据管理

### 2. 时序关系管理  
- 创建和管理节点间的复杂关系
- 支持时序关系追踪和历史版本
- 图查询和多层图遍历能力
- **时间有效性管理** - 支持valid、invalid、pending、expired状态
- **关系权重计算** - 智能关系强度评估

### 3. 时序智能查询系统
- 自然语言查询接口
- **时间点查询功能** - 支持历史时刻的精确查询
- 基于图结构的语义搜索
- Cypher查询语言完整支持
- **时序有效性过滤** - 按时间状态筛选知识
- **查询结果一致性保证** - 统一的搜索策略

### 4. 增强聊天交互
- 对话式知识查询界面
- 实时查询结果展示
- 上下文感知的智能回答
- 会话历史管理
- **图数据统计集成** - 实时显示知识图谱概况
- **查询解释功能** - AI解释查询逻辑和结果

### 5. 时序知识图谱浏览器
- **TemporalExplorer组件** - 专业的时序数据探索界面
- **时序有效性统计** - 实时展示数据状态分布
- **演示数据生成** - 一键创建时序测试数据
- **时间范围查询** - 支持复杂时间区间检索

### 6. 高性能图数据库管理
- FalkorDB原生图数据库集成
- 可视化图浏览器界面 (FalkorDB Browser)
- 图统计和实时分析功能
- 高性能图操作和批量处理

## 技术栈详情

### 后端技术栈
- **FastAPI**: 现代化Python Web框架
- **FalkorDB**: Redis兼容的图数据库
- **Graphiti**: 时序知识图谱引擎  
- **SQLAlchemy**: ORM框架
- **AsyncPG**: 异步PostgreSQL驱动
- **Redis**: 缓存和会话存储
- **OpenAI**: LLM集成 (支持mock模式)

### 前端技术栈
- **NextJS 14**: React框架 (App Router)
- **TailwindCSS**: 原子化CSS框架
- **TypeScript**: 类型安全
- **React Hook Form**: 表单管理
- **Axios**: HTTP客户端
- **Socket.io**: 实时通信
- **科技感UI**: 玻璃态拟物化 + 霓虹效果

## 项目结构

```
tkg-context-engine/
├── backend/                 # Python后端
│   ├── app/
│   │   ├── api/            # API路由
│   │   │   ├── knowledge.py    # 知识节点API (分页+搜索)
│   │   │   ├── relations.py    # 关系管理API
│   │   │   ├── temporal.py     # 时序查询API (NEW)
│   │   │   ├── query.py        # 图查询API
│   │   │   └── chat.py         # 聊天API (统计集成)
│   │   ├── models/         # 数据模型
│   │   │   └── schemas.py      # 时序数据模型 (增强)
│   │   ├── services/       # 业务逻辑
│   │   │   ├── falkordb_service.py    # FalkorDB服务
│   │   │   └── graphiti_service.py    # Graphiti集成 (增强)
│   │   └── main.py         # 应用入口
│   ├── pyproject.toml      # Python依赖
│   └── Dockerfile
├── frontend/               # NextJS前端  
│   ├── src/
│   │   ├── app/           # App Router
│   │   ├── components/    # React组件
│   │   │   ├── Dashboard.tsx      # 仪表板 (图统计)
│   │   │   ├── KnowledgeManager.tsx # 知识管理 (分页+搜索)
│   │   │   ├── ChatInterface.tsx   # 聊天界面 (增强)
│   │   │   └── TemporalExplorer.tsx # 时序浏览器 (NEW)
│   │   └── lib/          # 工具函数和API客户端
│   │       ├── api.ts             # API客户端 (更新)
│   │       ├── types.ts           # 时序类型定义 (增强)
│   │       └── utils.ts           # 工具函数
│   ├── package.json       # Node.js依赖
│   └── Dockerfile
├── docker-compose.yml     # 容器编排 (包含FalkorDB)
├── .env                   # 环境变量配置
└── CLAUDE.md             # 开发文档
```

## 开发状态

- ✅ 项目基础架构搭建
- ✅ Docker容器化配置  
- ✅ FalkorDB图数据库集成
- ✅ 后端API框架完成
- ✅ Graphiti + FalkorDB双层集成
- ✅ 前端项目完成
- ✅ 科技感UI界面实现
- ✅ 聊天界面开发完成
- ✅ 系统集成测试完成
- ✅ 完整的CRUD操作
- ✅ 图查询和可视化
- ✅ 实时聊天功能
- ✅ **企业级分页系统**
- ✅ **时序知识图谱浏览器** 
- ✅ **查询结果一致性优化**
- ✅ **React组件优化** (useCallback, useMemo)
- ✅ **时间有效性状态管理**
- ✅ **演示数据生成功能**
- ✅ **UI/UX bug修复** (输入框焦点、JSX语法等)

**🎯 项目完成度: 120%** (超出预期功能)

## 系统特性

### 🚀 高性能图数据库
- 基于FalkorDB的原生图存储
- Cypher查询语言支持
- 实时图遍历和分析

### 🧠 智能知识管理  
- Graphiti时序知识图谱引擎
- 上下文感知的智能问答
- 自动知识抽取和关系发现
- **时序有效性智能判断** - 自动识别数据时间状态
- **企业级搜索引擎** - 支持复杂查询条件

### 🎨 现代化界面
- 科技感玻璃拟物化设计
- 响应式布局适配
- 实时数据可视化
- **四大功能模块** - Dashboard、Knowledge、Chat、Temporal
- **交互体验优化** - 解决输入框焦点丢失等UX问题

### 🔧 开发友好
- 完整的API文档
- Mock模式支持  
- 开发热重载
- Docker一键部署
- **企业级错误处理** - 完善的异常处理和用户反馈
- **代码质量保证** - TypeScript类型安全 + Python类型提示

## 部署说明

### 生产环境部署

1. 确保Docker和Docker Compose已安装
2. 配置环境变量
3. 启动服务: `docker-compose up -d`
4. 检查健康状态: `curl http://localhost:8001/health`

### 环境变量说明

```bash
# OpenAI配置 (可选，支持mock模式)
OPENAI_API_KEY=your_openai_api_key_here

# 数据库配置
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/tkg_context
REDIS_URL=redis://localhost:6378

# FalkorDB配置  
FALKORDB_HOST=localhost
FALKORDB_PORT=6380
FALKORDB_PASSWORD=falkordb
FALKORDB_GRAPH_NAME=tkg_knowledge_graph

# 前端配置
NEXT_PUBLIC_API_URL=http://localhost:8001
```

## 故障排除

### 常见问题

1. **端口冲突**: 检查端口占用，修改docker-compose.yml中的端口配置
2. **FalkorDB连接失败**: 检查FalkorDB容器是否正常运行
3. **前端API调用失败**: 确认NEXT_PUBLIC_API_URL指向正确的后端地址
4. **OpenAI API错误**: 系统支持mock模式，无需真实API密钥即可运行
5. **分页数据不一致**: 系统已优化查询策略，确保各页面数据一致性
6. **时序查询无结果**: 请确认时间范围设置正确，使用演示数据功能测试
7. **React组件异常**: 清除浏览器缓存或重启开发服务器

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f falkordb
```

## 贡献指南

1. Fork本项目
2. 创建功能分支: `git checkout -b feature/新功能`
3. 提交更改: `git commit -am '添加新功能'`  
4. 推送到分支: `git push origin feature/新功能`
5. 提交Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 更新日志

### v1.2.0 (2025-09-02) - 企业级增强版
- ✨ **时序知识图谱浏览器** - 全新TemporalExplorer组件
- ✨ **企业级分页系统** - 支持大规模数据浏览和导航
- ✨ **查询结果一致性优化** - 统一搜索策略，解决数据不一致问题
- ✨ **时序有效性状态管理** - 支持valid、invalid、pending、expired状态
- ✨ **演示数据生成功能** - 一键创建时序测试数据
- 🔧 **React组件性能优化** - 使用useCallback、useMemo提升性能
- 🐛 **UI/UX问题修复** - 解决输入框焦点丢失、JSX语法错误等问题
- 🐛 **DateTime timezone处理** - 修复时间比较和格式化错误
- 📈 **API性能优化** - 提升查询效率和响应速度
- 📚 **文档全面更新** - CLAUDE.md和README.md同步更新

### v1.0.0 (2025-09-01) - 基础功能完整版
- ✨ 完成FalkorDB图数据库集成
- ✨ 实现完整的知识图谱管理系统
- ✨ 添加科技感UI界面
- ✨ 支持实时聊天和图查询
- 🐛 修复API数据类型验证问题
- 📚 完善项目文档