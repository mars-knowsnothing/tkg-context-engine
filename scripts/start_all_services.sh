#!/bin/bash

# TKG Context Engine - All-in-One Service Startup Script
# 启动所有服务：前端、后端和数据库

set -e  # Exit on any error

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目端口配置
FRONTEND_PORT=3000
BACKEND_PORT=8001
FALKORDB_PORT=6380
FALKORDB_BROWSER_PORT=3001
POSTGRES_PORT=5433
REDIS_PORT=6378

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# PID文件存储目录
PID_DIR="$PROJECT_ROOT/scripts/pids"

# 日志文件存储目录  
LOG_DIR="$PROJECT_ROOT/logs"

# 确保目录存在
mkdir -p "$PID_DIR" "$LOG_DIR"

echo -e "${PURPLE}================================${NC}"
echo -e "${PURPLE}🚀 TKG Context Engine Startup${NC}"
echo -e "${PURPLE}================================${NC}"
echo -e "${CYAN}项目路径: $PROJECT_ROOT${NC}"
echo

# 信号处理函数 - 清理所有进程
cleanup() {
    echo -e "\n${YELLOW}🛑 收到退出信号，正在清理所有服务...${NC}"
    
    # 停止所有后台进程
    stop_all_services
    
    # 清理PID文件
    rm -rf "$PID_DIR"
    
    echo -e "${GREEN}✅ 清理完成，退出程序${NC}"
    exit 0
}

# 注册信号处理
trap cleanup SIGINT SIGTERM

# 检查端口占用并清理
kill_port_processes() {
    local port=$1
    local service_name=$2
    
    echo -e "${YELLOW}🔍 检查端口 $port ($service_name)...${NC}"
    
    # 查找占用端口的进程
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        echo -e "${RED}❌ 端口 $port 被占用，进程ID: $pids${NC}"
        echo -e "${YELLOW}🗑️  正在清理端口 $port 的进程...${NC}"
        
        # 尝试优雅关闭
        for pid in $pids; do
            if kill -TERM "$pid" 2>/dev/null; then
                echo -e "${BLUE}📤 发送TERM信号到进程 $pid${NC}"
                sleep 2
                
                # 检查进程是否还在运行
                if kill -0 "$pid" 2>/dev/null; then
                    echo -e "${RED}🔨 强制终止进程 $pid${NC}"
                    kill -KILL "$pid" 2>/dev/null || true
                fi
            fi
        done
        
        # 再次检查端口
        sleep 1
        local remaining=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$remaining" ]; then
            echo -e "${RED}⚠️  端口 $port 仍被占用，请手动检查${NC}"
        else
            echo -e "${GREEN}✅ 端口 $port 已释放${NC}"
        fi
    else
        echo -e "${GREEN}✅ 端口 $port 可用${NC}"
    fi
}

# 清理所有端口和Docker服务
cleanup_ports() {
    echo -e "${BLUE}🧹 清理现有服务...${NC}"
    
    # 首先停止Docker服务（这会释放相关端口）
    echo -e "${YELLOW}🐳 停止现有Docker服务...${NC}"
    docker compose down --remove-orphans 2>/dev/null || docker-compose down --remove-orphans 2>/dev/null || true
    
    # 清理非Docker端口（前端、后端API）
    kill_port_processes $FRONTEND_PORT "Frontend"
    kill_port_processes $BACKEND_PORT "Backend API"
    
    echo -e "${GREEN}✅ 服务清理完成${NC}\n"
}

# 检查Docker服务状态
check_docker_services() {
    echo -e "${BLUE}🐳 启动数据库服务...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker未安装${NC}"
        exit 1
    fi
    
    # 检查Docker Compose命令
    local compose_cmd=""
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        compose_cmd="docker compose"
    elif command -v docker-compose &> /dev/null; then
        compose_cmd="docker-compose"
    else
        echo -e "${RED}❌ Docker Compose未安装${NC}"
        exit 1
    fi
    
    # 启动Docker服务（数据库相关）
    echo -e "${YELLOW}📦 启动数据库服务...${NC}"
    $compose_cmd up -d falkordb postgres redis
    
    # 等待服务健康检查
    echo -e "${YELLOW}⏳ 等待数据库服务启动...${NC}"
    
    local max_wait=60
    local wait_count=0
    
    while [ $wait_count -lt $max_wait ]; do
        if $compose_cmd ps | grep -q "healthy"; then
            echo -e "${GREEN}✅ 数据库服务启动完成${NC}"
            break
        fi
        
        echo -n "."
        sleep 2
        wait_count=$((wait_count + 2))
    done
    
    if [ $wait_count -ge $max_wait ]; then
        echo -e "${RED}❌ 数据库服务启动超时${NC}"
        echo -e "${YELLOW}🔍 检查Docker服务状态:${NC}"
        $compose_cmd ps
        exit 1
    fi
    
    echo
}

# 启动后端服务
start_backend() {
    echo -e "${BLUE}🔧 启动后端服务...${NC}"
    
    cd "$PROJECT_ROOT/backend"
    
    # 检查Python环境
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}❌ uv 未安装，请先安装 uv${NC}"
        exit 1
    fi
    
    # 安装依赖
    echo -e "${YELLOW}📦 安装Python依赖...${NC}"
    uv sync
    
    # 启动后端
    echo -e "${YELLOW}🚀 启动FastAPI后端 (端口 $BACKEND_PORT)...${NC}"
    nohup uv run uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload \
        > "$LOG_DIR/backend.log" 2>&1 &
    
    local backend_pid=$!
    echo $backend_pid > "$PID_DIR/backend.pid"
    
    echo -e "${GREEN}✅ 后端服务已启动 (PID: $backend_pid)${NC}"
    echo -e "${BLUE}📋 日志文件: $LOG_DIR/backend.log${NC}"
    
    # 等待后端服务启动
    echo -e "${YELLOW}⏳ 等待后端服务就绪...${NC}"
    local count=0
    while [ $count -lt 30 ]; do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 后端服务就绪${NC}"
            break
        fi
        echo -n "."
        sleep 2
        count=$((count + 1))
    done
    
    if [ $count -ge 30 ]; then
        echo -e "${RED}❌ 后端服务启动超时${NC}"
        echo -e "${YELLOW}🔍 检查日志: tail -f $LOG_DIR/backend.log${NC}"
        return 1
    fi
    
    echo
    cd "$PROJECT_ROOT"
}

# 启动前端服务
start_frontend() {
    echo -e "${BLUE}🎨 启动前端服务...${NC}"
    
    cd "$PROJECT_ROOT/frontend"
    
    # 检查Node.js环境
    if ! command -v yarn &> /dev/null; then
        echo -e "${RED}❌ yarn 未安装，请先安装 yarn${NC}"
        exit 1
    fi
    
    # 安装依赖
    echo -e "${YELLOW}📦 安装Node.js依赖...${NC}"
    yarn install
    
    # 启动前端
    echo -e "${YELLOW}🚀 启动NextJS前端 (端口 $FRONTEND_PORT)...${NC}"
    nohup yarn dev > "$LOG_DIR/frontend.log" 2>&1 &
    
    local frontend_pid=$!
    echo $frontend_pid > "$PID_DIR/frontend.pid"
    
    echo -e "${GREEN}✅ 前端服务已启动 (PID: $frontend_pid)${NC}"
    echo -e "${BLUE}📋 日志文件: $LOG_DIR/frontend.log${NC}"
    
    # 等待前端服务启动
    echo -e "${YELLOW}⏳ 等待前端服务就绪...${NC}"
    local count=0
    while [ $count -lt 60 ]; do
        if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 前端服务就绪${NC}"
            break
        fi
        echo -n "."
        sleep 2
        count=$((count + 1))
    done
    
    if [ $count -ge 60 ]; then
        echo -e "${YELLOW}⚠️  前端服务可能仍在启动中${NC}"
        echo -e "${YELLOW}🔍 检查日志: tail -f $LOG_DIR/frontend.log${NC}"
    fi
    
    echo
    cd "$PROJECT_ROOT"
}

# 显示服务状态
show_services_status() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}📊 服务状态总览${NC}"
    echo -e "${PURPLE}================================${NC}"
    
    echo -e "${CYAN}🌐 前端应用:${NC} http://localhost:$FRONTEND_PORT"
    echo -e "${CYAN}🔧 后端API:${NC} http://localhost:$BACKEND_PORT"
    echo -e "${CYAN}📚 API文档:${NC} http://localhost:$BACKEND_PORT/docs"
    echo -e "${CYAN}📊 FalkorDB浏览器:${NC} http://localhost:$FALKORDB_BROWSER_PORT"
    
    echo
    echo -e "${BLUE}📋 运行中的服务进程:${NC}"
    
    if [ -f "$PID_DIR/backend.pid" ]; then
        local backend_pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$backend_pid" 2>/dev/null; then
            echo -e "${GREEN}✅ 后端服务 (PID: $backend_pid)${NC}"
        else
            echo -e "${RED}❌ 后端服务 (已停止)${NC}"
        fi
    fi
    
    if [ -f "$PID_DIR/frontend.pid" ]; then
        local frontend_pid=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$frontend_pid" 2>/dev/null; then
            echo -e "${GREEN}✅ 前端服务 (PID: $frontend_pid)${NC}"
        else
            echo -e "${RED}❌ 前端服务 (已停止)${NC}"
        fi
    fi
    
    echo
    echo -e "${BLUE}🐳 Docker服务状态:${NC}"
    
    # 检查Docker Compose命令并显示状态
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose ps
    elif command -v docker-compose &> /dev/null; then
        docker-compose ps
    fi
    
    echo
    echo -e "${PURPLE}================================${NC}"
    echo -e "${GREEN}🎉 所有服务启动完成！${NC}"
    echo -e "${YELLOW}💡 按 Ctrl+C 退出并停止所有服务${NC}"
    echo -e "${PURPLE}================================${NC}"
}

# 停止所有服务
stop_all_services() {
    echo -e "${YELLOW}🛑 正在停止所有服务...${NC}"
    
    # 停止前端进程
    if [ -f "$PID_DIR/frontend.pid" ]; then
        local frontend_pid=$(cat "$PID_DIR/frontend.pid")
        if kill -0 "$frontend_pid" 2>/dev/null; then
            echo -e "${BLUE}🛑 停止前端服务 (PID: $frontend_pid)${NC}"
            kill -TERM "$frontend_pid" 2>/dev/null || true
            sleep 2
            kill -KILL "$frontend_pid" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/frontend.pid"
    fi
    
    # 停止后端进程
    if [ -f "$PID_DIR/backend.pid" ]; then
        local backend_pid=$(cat "$PID_DIR/backend.pid")
        if kill -0 "$backend_pid" 2>/dev/null; then
            echo -e "${BLUE}🛑 停止后端服务 (PID: $backend_pid)${NC}"
            kill -TERM "$backend_pid" 2>/dev/null || true
            sleep 2
            kill -KILL "$backend_pid" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/backend.pid"
    fi
    
    # 停止Docker服务
    echo -e "${BLUE}🐳 停止Docker服务...${NC}"
    
    # 检查Docker Compose命令并停止服务
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        docker compose down --remove-orphans
    elif command -v docker-compose &> /dev/null; then
        docker-compose down --remove-orphans
    else
        echo -e "${YELLOW}⚠️  未找到Docker Compose命令${NC}"
    fi
    
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

# 监控服务运行状态
monitor_services() {
    while true; do
        sleep 10
        
        # 检查进程是否还在运行
        local backend_running=false
        local frontend_running=false
        
        if [ -f "$PID_DIR/backend.pid" ]; then
            local backend_pid=$(cat "$PID_DIR/backend.pid")
            if kill -0 "$backend_pid" 2>/dev/null; then
                backend_running=true
            fi
        fi
        
        if [ -f "$PID_DIR/frontend.pid" ]; then
            local frontend_pid=$(cat "$PID_DIR/frontend.pid")
            if kill -0 "$frontend_pid" 2>/dev/null; then
                frontend_running=true
            fi
        fi
        
        if [ "$backend_running" = false ] || [ "$frontend_running" = false ]; then
            echo -e "\n${RED}❌ 检测到服务异常退出${NC}"
            if [ "$backend_running" = false ]; then
                echo -e "${RED}❌ 后端服务已停止${NC}"
            fi
            if [ "$frontend_running" = false ]; then
                echo -e "${RED}❌ 前端服务已停止${NC}"
            fi
            
            echo -e "${YELLOW}🔍 检查日志文件获取更多信息:${NC}"
            echo -e "${CYAN}  - 后端日志: $LOG_DIR/backend.log${NC}"
            echo -e "${CYAN}  - 前端日志: $LOG_DIR/frontend.log${NC}"
            
            cleanup
        fi
    done
}

# 主函数
main() {
    echo -e "${BLUE}🚀 开始启动TKG Context Engine服务...${NC}\n"
    
    # 1. 清理端口占用
    cleanup_ports
    
    # 2. 检查并启动Docker服务
    check_docker_services
    
    # 3. 启动后端服务
    if ! start_backend; then
        echo -e "${RED}❌ 后端启动失败${NC}"
        exit 1
    fi
    
    # 4. 启动前端服务
    start_frontend
    
    # 5. 显示服务状态
    show_services_status
    
    # 6. 监控服务运行状态
    monitor_services
}

# 检查命令行参数
case "${1:-}" in
    "stop")
        echo -e "${YELLOW}🛑 停止所有服务...${NC}"
        stop_all_services
        exit 0
        ;;
    "status")
        show_services_status
        exit 0
        ;;
    "help"|"-h"|"--help")
        echo "TKG Context Engine 服务管理脚本"
        echo
        echo "用法:"
        echo "  $0          启动所有服务"
        echo "  $0 stop     停止所有服务"
        echo "  $0 status   显示服务状态"
        echo "  $0 help     显示帮助信息"
        echo
        exit 0
        ;;
    "")
        main
        ;;
    *)
        echo -e "${RED}❌ 未知参数: $1${NC}"
        echo "使用 '$0 help' 查看帮助"
        exit 1
        ;;
esac