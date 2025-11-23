#!/bin/bash
# Markdown 搜索引擎健康检查脚本
# 用法: ./health_check.sh [endpoint]

set -e

# 配置
ENDPOINT="${1:-http://localhost:8000}"
TIMEOUT=10
SEARCH_TEST_QUERY="test"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查计数器
CHECKS_PASSED=0
CHECKS_FAILED=0

# 检查函数
check_endpoint() {
    local url=$1
    local description=$2
    local expected_code=${3:-200}
    
    log_info "检查: $description"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$url" 2>/dev/null)
    
    if [ "$response" -eq "$expected_code" ]; then
        log_info "✓ $description - OK (HTTP $response)"
        ((CHECKS_PASSED++))
        return 0
    else
        log_error "✗ $description - FAILED (HTTP $response, expected $expected_code)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# 检查响应时间
check_response_time() {
    local url=$1
    local description=$2
    local max_time=${3:-1000}  # 毫秒
    
    log_info "检查: $description"
    
    response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time $TIMEOUT "$url" 2>/dev/null)
    response_time_ms=$(echo "$response_time * 1000" | bc | cut -d. -f1)
    
    if [ "$response_time_ms" -lt "$max_time" ]; then
        log_info "✓ $description - OK (${response_time_ms}ms)"
        ((CHECKS_PASSED++))
        return 0
    else
        log_warn "✗ $description - SLOW (${response_time_ms}ms, expected <${max_time}ms)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# 检查 JSON 响应
check_json_response() {
    local url=$1
    local description=$2
    
    log_info "检查: $description"
    
    response=$(curl -s --max-time $TIMEOUT "$url" 2>/dev/null)
    
    if echo "$response" | python3 -m json.tool > /dev/null 2>&1; then
        log_info "✓ $description - OK (valid JSON)"
        ((CHECKS_PASSED++))
        return 0
    else
        log_error "✗ $description - FAILED (invalid JSON)"
        ((CHECKS_FAILED++))
        return 1
    fi
}

echo "========================================"
echo "Markdown 搜索引擎健康检查"
echo "========================================"
echo "端点: $ENDPOINT"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 1. 检查主页
check_endpoint "$ENDPOINT/" "主页访问"

# 2. 检查 API 文档
check_endpoint "$ENDPOINT/docs" "API 文档"

# 3. 检查搜索端点（空查询应该返回 422）
check_endpoint "$ENDPOINT/search?q=" "空查询验证" 422

# 4. 检查搜索功能
check_endpoint "$ENDPOINT/search?q=$SEARCH_TEST_QUERY" "搜索功能"

# 5. 检查搜索 JSON 响应
check_json_response "$ENDPOINT/search?q=$SEARCH_TEST_QUERY" "搜索 JSON 格式"

# 6. 检查响应时间
check_response_time "$ENDPOINT/" "主页响应时间" 1000

# 7. 检查搜索响应时间
check_response_time "$ENDPOINT/search?q=$SEARCH_TEST_QUERY" "搜索响应时间" 2000

# 8. 检查静态文件
check_endpoint "$ENDPOINT/static/style.css" "静态文件访问"

echo ""
echo "========================================"
echo "健康检查结果"
echo "========================================"
echo -e "通过: ${GREEN}$CHECKS_PASSED${NC}"
echo -e "失败: ${RED}$CHECKS_FAILED${NC}"
echo "========================================"

# 返回状态码
if [ $CHECKS_FAILED -eq 0 ]; then
    log_info "所有检查通过！服务健康。"
    exit 0
else
    log_error "有 $CHECKS_FAILED 项检查失败！"
    exit 1
fi
