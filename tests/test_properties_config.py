"""属性测试：配置管理功能

使用 Hypothesis 进行基于属性的测试。
每个测试运行至少 100 次迭代以验证属性在各种输入下都成立。
"""

import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from pydantic import ValidationError

from app.config import Settings


# Feature: md-search-engine, Property 13: 配置重载生效
# Validates: Requirements 7.4
@settings(max_examples=100)
@given(
    # 生成初始配置值
    initial_log_level=st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    initial_max_limit=st.integers(min_value=1, max_value=1000),
    initial_snippet_tokens=st.integers(min_value=1, max_value=100),
    # 生成修改后的配置值（确保与初始值不同）
    new_log_level=st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    new_max_limit=st.integers(min_value=1, max_value=1000),
    new_snippet_tokens=st.integers(min_value=1, max_value=100),
)
def test_property_config_reload_applies_changes(
    initial_log_level,
    initial_max_limit,
    initial_snippet_tokens,
    new_log_level,
    new_max_limit,
    new_snippet_tokens
):
    """属性测试：配置重载生效
    
    属性：对于任意配置修改，
    系统重启后应使用新的配置值。
    
    验证需求: 7.4 - WHERE 用户修改配置文件 THEN 系统 SHALL 在重启后应用新配置
    """
    # 为每个测试用例创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        
        # 创建必需的目录
        md_root = temp_dir / "docs"
        md_root.mkdir()
        
        db_dir = temp_dir / "data"
        db_dir.mkdir()
        db_path = db_dir / "test.db"
        
        # 第一阶段：创建初始配置文件
        env_file = temp_dir / ".env"
        initial_config = f"""MD_ROOT={md_root}
DB_PATH={db_path}
LOG_LEVEL={initial_log_level}
MAX_SEARCH_LIMIT={initial_max_limit}
SNIPPET_TOKENS={initial_snippet_tokens}
"""
        env_file.write_text(initial_config, encoding='utf-8')
        
        # 加载初始配置（模拟系统首次启动）
        initial_settings = Settings(_env_file=str(env_file))
        
        # 验证初始配置值
        assert initial_settings.log_level == initial_log_level
        assert initial_settings.max_search_limit == initial_max_limit
        assert initial_settings.snippet_tokens == initial_snippet_tokens
        
        # 第二阶段：修改配置文件（模拟用户修改配置）
        new_config = f"""MD_ROOT={md_root}
DB_PATH={db_path}
LOG_LEVEL={new_log_level}
MAX_SEARCH_LIMIT={new_max_limit}
SNIPPET_TOKENS={new_snippet_tokens}
"""
        env_file.write_text(new_config, encoding='utf-8')
        
        # 第三阶段：重新加载配置（模拟系统重启）
        reloaded_settings = Settings(_env_file=str(env_file))
        
        # 验证属性：重启后应使用新的配置值
        assert reloaded_settings.log_level == new_log_level, \
            f"Expected log_level to be '{new_log_level}' after reload, but got '{reloaded_settings.log_level}'"
        
        assert reloaded_settings.max_search_limit == new_max_limit, \
            f"Expected max_search_limit to be {new_max_limit} after reload, but got {reloaded_settings.max_search_limit}"
        
        assert reloaded_settings.snippet_tokens == new_snippet_tokens, \
            f"Expected snippet_tokens to be {new_snippet_tokens} after reload, but got {reloaded_settings.snippet_tokens}"
        
        # 验证路径配置也正确保持
        assert reloaded_settings.md_root == md_root
        assert reloaded_settings.db_path == db_path
