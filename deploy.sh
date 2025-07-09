#!/bin/bash

# SAP AI Agent Docker 部署腳本
# 此腳本提供簡單的容器管理功能

set -e

# 顏色設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函數：印出彩色訊息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 函數：檢查 Docker 是否已安裝
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安裝，請先安裝 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose 未安裝，請先安裝 Docker Compose"
        exit 1
    fi
}

# 函數：建立環境變數檔案
create_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env 檔案不存在，從範例檔案創建"
        if [ -f env.example ]; then
            cp env.example .env
            print_info "已創建 .env 檔案，請編輯設定您的環境變數"
        else
            print_error "找不到 env.example 檔案"
            exit 1
        fi
    fi
}

# 函數：建立必要的目錄
create_directories() {
    print_info "創建必要的目錄..."
    mkdir -p logs
    print_success "目錄創建完成"
}

# 函數：建構 Docker 映像檔
build() {
    print_info "開始建構 Docker 映像檔..."
    docker-compose build --no-cache
    print_success "Docker 映像檔建構完成"
}

# 函數：啟動服務
start() {
    print_info "啟動 SAP AI Agent 服務..."
    docker-compose up -d
    print_success "服務已啟動"
    print_info "應用程式可在 http://localhost:7777 存取"
}

# 函數：停止服務
stop() {
    print_info "停止 SAP AI Agent 服務..."
    docker-compose down
    print_success "服務已停止"
}

# 函數：重新啟動服務
restart() {
    print_info "重新啟動 SAP AI Agent 服務..."
    stop
    start
    print_success "服務已重新啟動"
}

# 函數：查看服務狀態
status() {
    print_info "服務狀態："
    docker-compose ps
}

# 函數：查看日誌
logs() {
    print_info "查看服務日誌 (按 Ctrl+C 退出)："
    docker-compose logs -f
}

# 函數：進入容器
shell() {
    print_info "進入應用程式容器..."
    docker-compose exec sap-ai-agent /bin/bash
}

# 函數：清理
clean() {
    print_warning "這將刪除所有容器、映像檔和卷，確定要繼續嗎？ (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_info "清理 Docker 資源..."
        docker-compose down -v --rmi all
        print_success "清理完成"
    else
        print_info "清理已取消"
    fi
}

# 函數：顯示使用說明
usage() {
    echo "SAP AI Agent Docker 管理腳本"
    echo ""
    echo "使用方法: $0 [命令]"
    echo ""
    echo "可用命令："
    echo "  setup    - 初始設定（創建環境變數檔案和目錄）"
    echo "  build    - 建構 Docker 映像檔"
    echo "  start    - 啟動服務"
    echo "  stop     - 停止服務"
    echo "  restart  - 重新啟動服務"
    echo "  status   - 查看服務狀態"
    echo "  logs     - 查看服務日誌"
    echo "  shell    - 進入應用程式容器"
    echo "  clean    - 清理所有 Docker 資源"
    echo "  deploy   - 完整部署（setup + build + start）"
    echo "  help     - 顯示此說明"
    echo ""
}

# 主程式
main() {
    case "${1:-help}" in
        setup)
            check_docker
            create_env_file
            create_directories
            print_success "初始設定完成"
            ;;
        build)
            check_docker
            build
            ;;
        start)
            check_docker
            start
            ;;
        stop)
            check_docker
            stop
            ;;
        restart)
            check_docker
            restart
            ;;
        status)
            check_docker
            status
            ;;
        logs)
            check_docker
            logs
            ;;
        shell)
            check_docker
            shell
            ;;
        clean)
            check_docker
            clean
            ;;
        deploy)
            check_docker
            create_env_file
            create_directories
            build
            start
            print_success "部署完成！應用程式可在 http://localhost:7777 存取"
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            print_error "未知命令: $1"
            usage
            exit 1
            ;;
    esac
}

# 執行主程式
main "$@"
