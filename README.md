# TKG Context Engine

时序知识图谱上下文引擎 - 基于 Graphiti 的智能知识管理系统

## 架构概述

- **后端**: FastAPI + Python 3.12 + Graphiti
- **前端**: NextJS 14 + TailwindCSS + TypeScript
- **数据库**: PostgreSQL + Redis
- **依赖管理**: uv (后端) + yarn (前端)

## 快速开始

### 环境准备

1. 复制环境变量模板:
```bash
cp .env.example .env
```

2. 配置OpenAI API密钥:
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

### 本地开发

#### 后端开发

```bash
cd backend

# 安装依赖 (使用 uv)
uv sync

# 启动开发服务器
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 主要功能

### 1. 知识节点管理
- 创建、查询、更新、删除知识节点
- 支持实体、事件、概念等不同类型

### 2. 关系管理  
- 创建和管理节点间的关系
- 支持时序关系追踪

### 3. 智能查询
- 自然语言查询接口
- 时间点查询功能
- 语义搜索能力

### 4. 聊天交互
- 对话式知识查询
- 实时查询结果展示

## 技术栈详情

### 后端技术栈
- **FastAPI**: 现代化Python Web框架
- **Graphiti**: 时序知识图谱引擎  
- **SQLAlchemy**: ORM框架
- **AsyncPG**: 异步PostgreSQL驱动
- **Redis**: 缓存和会话存储
- **OpenAI**: LLM集成

### 前端技术栈
- **NextJS 14**: React框架 (App Router)
- **TailwindCSS**: 原子化CSS框架
- **TypeScript**: 类型安全
- **React Hook Form**: 表单管理
- **Axios**: HTTP客户端
- **Socket.io**: 实时通信

## 项目结构

```
tkg-context-engine/
├── backend/                 # Python后端
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── main.py         # 应用入口
│   ├── pyproject.toml      # Python依赖
│   └── Dockerfile
├── frontend/               # NextJS前端  
│   ├── src/
│   │   ├── app/           # App Router
│   │   ├── components/    # React组件
│   │   └── lib/          # 工具函数
│   ├── package.json       # Node.js依赖
│   └── Dockerfile
├── docker-compose.yml     # 容器编排
└── .env.example          # 环境变量模板
```

## 开发状态

- ✅ 项目基础架构搭建
- ✅ Docker容器化配置
- ✅ 后端API框架完成
- ✅ Graphiti集成完成
- ✅ 前端项目初始化
- 🔄 前端UI组件开发中
- ⏳ 聊天界面开发待完成
- ⏳ 系统集成测试待完成