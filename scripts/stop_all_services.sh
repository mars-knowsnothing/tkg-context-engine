#!/bin/bash

# TKG Context Engine - Quick Stop Script
# 快速停止所有相关服务和进程

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🛑 停止TKG Context Engine所有服务${NC}"

# 停止Docker服务（优先使用docker compose down清理）
echo -e "${BLUE}🐳 停止Docker服务...${NC}"
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose down --remove-orphans 2>/dev/null || true
elif command -v docker-compose &> /dev/null; then
    docker-compose down --remove-orphans 2>/dev/null || true
else
    echo -e "${YELLOW}⚠️  未找到Docker Compose命令，跳过Docker服务清理${NC}"
fi

# 停止本地开发服务端口的进程（前端、后端）
LOCAL_PORTS=(3000 8001)
LOCAL_PORT_NAMES=("Frontend" "Backend")

for i in "${!LOCAL_PORTS[@]}"; do
    port=${LOCAL_PORTS[$i]}
    name=${LOCAL_PORT_NAMES[$i]}
    
    echo -e "${YELLOW}🔍 检查端口 $port ($name)...${NC}"
    pids=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        echo -e "${BLUE}🗑️  终止端口 $port 的进程: $pids${NC}"
        for pid in $pids; do
            kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
        done
    else
        echo -e "${GREEN}✅ 端口 $port 无进程占用${NC}"
    fi
done

# 清理PID文件
echo -e "${YELLOW}🗂️  清理PID文件...${NC}"
rm -rf scripts/pids 2>/dev/null || true

# 停止可能的node和python进程（谨慎操作）
echo -e "${YELLOW}🔍 查找相关Node.js和Python进程...${NC}"

# 查找可能的相关进程（限制搜索范围避免误杀）
node_pids=$(pgrep -f "yarn dev\|next dev\|uvicorn.*tkg\|app.main" 2>/dev/null || true)
if [ -n "$node_pids" ]; then
    echo -e "${BLUE}🗑️  发现相关进程: $node_pids${NC}"
    for pid in $node_pids; do
        echo -e "${YELLOW}终止进程 $pid${NC}"
        kill -TERM "$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    done
else
    echo -e "${GREEN}✅ 未发现相关开发进程${NC}"
fi

echo -e "${GREEN}✅ 清理完成${NC}"
echo -e "${BLUE}💡 Docker服务已通过 docker compose down 清理${NC}"
echo -e "${BLUE}💡 本地开发服务进程已终止${NC}"