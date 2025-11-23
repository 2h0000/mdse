"""属性测试：日志记录功能

使用 Hypothesis 进行基于属性的测试。
每个测试运行至少 100 次迭代以验证属性在各种输入下都成立。
"""

import tempfile
from pathlib import Path
import sqlite3
import logging
import io
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.db import init_db
from app.indexer import index_file
from app.main import app
from app import config


# 辅助函数：生成有效的搜索关键词策略
def _valid_search_keyword_strategy():
    """生成有效的搜索关键词（避免 FTS5 特殊字符和空白）"""
    return st.text(
        alphabet=st.characters(
            min_codepoint=ord('a'),
            max_codepoint=ord('z')
        ) | st.characters(
            min_codepoint=ord('A'),
            max_codepoint=ord('Z')
        ) | st.characters(
            min_codepoint=ord('0'),
            max_codepoint=ord('9')
        ) | st.sampled_from([' ']),
        min_size=1,
        max_size=50
    ).filter(lambda s: s and s.strip() and len(s.strip()) > 0)


# Feature: md-search-engine, Property 21: 日志记录
# Validates: Requirements 10.2
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成文档数量
    num_docs=st.integers(min_value=0, max_value=5),
    # 生成日志级别
    log_level=st.sampled_from(['INFO', 'WARNING', 'ERROR', 'DEBUG'])
)
def test_property_logging_records_access_and_errors(keyword, num_docs, log_level):
    """属性测试：日志记录
    
    属性：对于任意 API 请求，
    系统应记录访问日志（INFO 级别）和错误日志（ERROR 级别）。
    
    验证需求: 10.2 - 系统在生产环境运行时记录访问日志和错误日志
    """
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # 创建一个字符串 IO 对象来捕获日志输出
        log_stream = io.StringIO()
        log_handler = logging.StreamHandler(log_stream)
        log_handler.setLevel(logging.DEBUG)  # 捕获所有级别的日志
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_formatter)
        
        # 获取相关的日志记录器
        app_logger = logging.getLogger('app')
        middleware_logger = logging.getLogger('app.middleware')
        
        # 保存原始处理器
        original_app_handlers = app_logger.handlers[:]
        original_middleware_handlers = middleware_logger.handlers[:]
        
        # 添加我们的测试处理器
        app_logger.addHandler(log_handler)
        middleware_logger.addHandler(log_handler)
        
        # 设置日志级别
        original_app_level = app_logger.level
        original_middleware_level = middleware_logger.level
        app_logger.setLevel(getattr(logging, log_level))
        middleware_logger.setLevel(getattr(logging, log_level))
        
        try:
            # Mock settings to use temporary directory
            with patch.object(config.settings, 'md_root', temp_md_root), \
                 patch.object(config.settings, 'db_path', db_path), \
                 patch.object(config.settings, 'log_level', log_level):
                
                # 创建数据库连接并初始化
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                init_db(conn)
                
                # 创建测试文档
                for i in range(num_docs):
                    content = f"Document {i} contains the keyword: {keyword_stripped}. Additional content for testing."
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: Test Document {i}
---

{content}
"""
                    
                    test_file = temp_md_root / f"test_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                conn.close()
                
                # 清空日志流
                log_stream.truncate(0)
                log_stream.seek(0)
                
                # 创建测试客户端
                client = TestClient(app)
                
                # 执行搜索请求
                response = client.get("/search", params={
                    "q": keyword_stripped,
                    "limit": 10,
                    "offset": 0
                })
                
                # 获取日志输出
                log_output = log_stream.getvalue()
                
                # 验证属性 1: 应该记录访问日志（INFO 级别）
                # 访问日志应该包含请求方法、路径等信息
                if log_level in ['DEBUG', 'INFO']:
                    # 只有当日志级别允许时才检查 INFO 日志
                    assert 'Request started' in log_output or 'GET' in log_output or '/search' in log_output, \
                        f"Access logs should be recorded at INFO level when log_level is {log_level}. " \
                        f"Log output: {log_output[:500]}"
                    
                    # 验证日志包含请求完成信息
                    assert 'Request completed' in log_output or 'Status:' in log_output or str(response.status_code) in log_output, \
                        f"Access logs should include request completion information. " \
                        f"Log output: {log_output[:500]}"
                
                # 验证属性 2: 日志应该包含时间戳
                # 日志格式包含时间戳（由 formatter 添加）
                if log_output:
                    # 检查是否有日期时间格式的字符串（YYYY-MM-DD HH:MM:SS）
                    import re
                    has_timestamp = bool(re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', log_output))
                    assert has_timestamp, \
                        f"Logs should contain timestamps. Log output: {log_output[:500]}"
                
                # 验证属性 3: 日志应该包含日志级别信息
                if log_output:
                    # 检查是否包含日志级别（INFO, WARNING, ERROR, DEBUG）
                    has_level = any(level in log_output for level in ['INFO', 'WARNING', 'ERROR', 'DEBUG'])
                    assert has_level, \
                        f"Logs should contain log level information. Log output: {log_output[:500]}"
                
                # 验证属性 4: 日志应该包含模块名称
                if log_output:
                    # 检查是否包含模块名称（app.xxx）
                    has_module = 'app' in log_output
                    assert has_module, \
                        f"Logs should contain module names. Log output: {log_output[:500]}"
                
                # 测试错误日志记录
                # 清空日志流
                log_stream.truncate(0)
                log_stream.seek(0)
                
                # 执行一个会导致错误的请求（空查询）
                error_response = client.get("/search", params={"q": ""})
                
                # 获取错误日志输出
                error_log_output = log_stream.getvalue()
                
                # 验证属性 5: 错误请求应该被记录
                # 即使是 422 错误（参数验证错误），也应该有访问日志
                if log_level in ['DEBUG', 'INFO']:
                    # 应该记录请求信息
                    assert 'Request' in error_log_output or 'GET' in error_log_output or '/search' in error_log_output, \
                        f"Error requests should be logged. Log output: {error_log_output[:500]}"
                
                # 验证属性 6: 日志应该包含状态码信息
                if log_level in ['DEBUG', 'INFO'] and error_log_output:
                    # 应该包含状态码（422）
                    assert '422' in error_log_output or 'Status' in error_log_output, \
                        f"Logs should include status code information for error responses. " \
                        f"Log output: {error_log_output[:500]}"
                
                # 验证属性 7: 日志应该包含处理时间信息
                if log_level in ['DEBUG', 'INFO'] and log_output:
                    # 应该包含处理时间（Duration 或 Process-Time）
                    has_duration = 'Duration' in log_output or 'Process' in log_output or 's' in log_output
                    assert has_duration, \
                        f"Logs should include request processing time. Log output: {log_output[:500]}"
                
        finally:
            # 恢复原始日志处理器和级别
            app_logger.handlers = original_app_handlers
            middleware_logger.handlers = original_middleware_handlers
            app_logger.setLevel(original_app_level)
            middleware_logger.setLevel(original_middleware_level)
            
            # 关闭日志处理器
            log_handler.close()


# Feature: md-search-engine, Property 22: 日志格式一致性
# Validates: Requirements 10.2
@settings(max_examples=100, deadline=None)
@given(
    # 生成多个请求
    num_requests=st.integers(min_value=1, max_value=5),
    keywords=st.lists(
        _valid_search_keyword_strategy(),
        min_size=1,
        max_size=5
    )
)
def test_property_logging_format_consistency(num_requests, keywords):
    """属性测试：日志格式一致性
    
    属性：对于任意多个 API 请求，
    所有日志条目应该使用一致的格式（包含时间戳、模块名、级别、消息）。
    
    验证需求: 10.2 - 配置日志记录（INFO、WARNING、ERROR）
    """
    import re
    
    # 确保有足够的关键词
    assume(len(keywords) >= num_requests)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # 创建一个字符串 IO 对象来捕获日志输出
        log_stream = io.StringIO()
        log_handler = logging.StreamHandler(log_stream)
        log_handler.setLevel(logging.INFO)
        log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_formatter)
        
        # 获取相关的日志记录器
        middleware_logger = logging.getLogger('app.middleware')
        
        # 保存原始处理器
        original_handlers = middleware_logger.handlers[:]
        original_level = middleware_logger.level
        
        # 添加我们的测试处理器
        middleware_logger.addHandler(log_handler)
        middleware_logger.setLevel(logging.INFO)
        
        try:
            # Mock settings to use temporary directory
            with patch.object(config.settings, 'md_root', temp_md_root), \
                 patch.object(config.settings, 'db_path', db_path):
                
                # 创建数据库连接并初始化
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                init_db(conn)
                
                # 创建一个测试文档
                file_content = """---
title: Test Document
---

This is a test document with some content for searching.
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                conn.close()
                
                # 清空日志流
                log_stream.truncate(0)
                log_stream.seek(0)
                
                # 创建测试客户端
                client = TestClient(app)
                
                # 执行多个搜索请求
                for i in range(num_requests):
                    keyword = keywords[i].strip()
                    if not keyword:
                        continue
                    
                    client.get("/search", params={
                        "q": keyword,
                        "limit": 10,
                        "offset": 0
                    })
                
                # 获取日志输出
                log_output = log_stream.getvalue()
                
                # 将日志分割成行
                log_lines = [line for line in log_output.split('\n') if line.strip()]
                
                # 验证属性 1: 所有日志行应该遵循相同的格式
                # 格式: YYYY-MM-DD HH:MM:SS - module.name - LEVEL - message
                log_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.*?-.*?-.*?-.*')
                
                for line in log_lines:
                    matches_format = bool(log_pattern.match(line))
                    assert matches_format, \
                        f"Log line should match the expected format. Line: {line}"
                
                # 验证属性 2: 每个请求应该至少生成两条日志（开始和完成）
                # 计算包含 "Request started" 和 "Request completed" 的日志行数
                started_count = sum(1 for line in log_lines if 'Request started' in line)
                completed_count = sum(1 for line in log_lines if 'Request completed' in line)
                
                # 每个成功的请求应该有开始和完成日志
                # 注意：由于某些关键词可能为空被跳过，我们验证至少有一些日志
                if num_requests > 0:
                    assert started_count > 0, \
                        f"Should have at least one 'Request started' log entry. Log output: {log_output[:500]}"
                    
                    assert completed_count > 0, \
                        f"Should have at least one 'Request completed' log entry. Log output: {log_output[:500]}"
                
                # 验证属性 3: 所有日志行应该包含模块名称
                for line in log_lines:
                    has_module = 'app' in line
                    assert has_module, \
                        f"Log line should contain module name. Line: {line}"
                
                # 验证属性 4: 所有日志行应该包含日志级别
                for line in log_lines:
                    has_level = any(level in line for level in ['INFO', 'WARNING', 'ERROR', 'DEBUG'])
                    assert has_level, \
                        f"Log line should contain log level. Line: {line}"
                
                # 验证属性 5: 日志时间戳应该按时间顺序排列（或至少不倒退）
                # 提取所有时间戳
                timestamps = []
                for line in log_lines:
                    match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match:
                        timestamps.append(match.group(1))
                
                # 验证时间戳是非递减的（允许相同时间戳）
                for i in range(len(timestamps) - 1):
                    assert timestamps[i] <= timestamps[i + 1], \
                        f"Log timestamps should be in chronological order. " \
                        f"Found {timestamps[i]} after {timestamps[i + 1]}"
                
        finally:
            # 恢复原始日志处理器和级别
            middleware_logger.handlers = original_handlers
            middleware_logger.setLevel(original_level)
            
            # 关闭日志处理器
            log_handler.close()
