"""安全功能测试

测试安全相关的验证和防护功能。
"""

import pytest
from pathlib import Path
from app.security import (
    validate_query_length,
    validate_path_traversal,
    SecurityError,
    MAX_QUERY_LENGTH,
    MAX_PATH_LENGTH
)


class TestQueryLengthValidation:
    """测试查询字符串长度验证"""
    
    def test_valid_query_length(self):
        """测试有效的查询字符串长度"""
        # 正常长度的查询应该通过
        query = "test query"
        validate_query_length(query)  # 不应抛出异常
    
    def test_max_query_length(self):
        """测试最大允许长度的查询"""
        # 最大长度的查询应该通过
        query = "a" * MAX_QUERY_LENGTH
        validate_query_length(query)  # 不应抛出异常
    
    def test_query_too_long(self):
        """测试超长查询字符串"""
        # 超过最大长度的查询应该被拒绝
        query = "a" * (MAX_QUERY_LENGTH + 1)
        with pytest.raises(SecurityError) as exc_info:
            validate_query_length(query)
        assert "too long" in str(exc_info.value).lower()
    
    def test_empty_query(self):
        """测试空查询字符串"""
        # 空查询应该通过长度验证（但会在其他地方被拒绝）
        validate_query_length("")  # 不应抛出异常
    
    def test_chinese_query_length(self):
        """测试中文查询字符串长度"""
        # 中文字符也应该正确计算长度
        query = "测试" * 100  # 200 个中文字符
        validate_query_length(query)  # 不应抛出异常


class TestPathTraversalValidation:
    """测试路径遍历防护"""
    
    def test_valid_relative_path(self, tmp_path):
        """测试有效的相对路径"""
        # 创建测试目录和文件
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        test_file = test_dir / "test.md"
        test_file.write_text("test content")
        
        # 临时修改 settings
        from app import config
        original_md_root = config.settings.md_root
        try:
            config.settings.md_root = test_dir
            
            # 有效的相对路径应该通过
            result = validate_path_traversal("test.md")
            assert result.exists()
            assert result.name == "test.md"
        finally:
            config.settings.md_root = original_md_root
    
    def test_path_traversal_attempt(self, tmp_path):
        """测试路径遍历攻击尝试"""
        # 创建测试目录
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        
        # 临时修改 settings
        from app import config
        original_md_root = config.settings.md_root
        try:
            config.settings.md_root = test_dir
            
            # 尝试访问父目录应该被拒绝
            with pytest.raises(SecurityError) as exc_info:
                validate_path_traversal("../../../etc/passwd")
            assert "outside" in str(exc_info.value).lower()
        finally:
            config.settings.md_root = original_md_root
    
    def test_absolute_path_outside_root(self, tmp_path):
        """测试指向根目录外的绝对路径"""
        # 创建测试目录
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        
        # 临时修改 settings
        from app import config
        original_md_root = config.settings.md_root
        try:
            config.settings.md_root = test_dir
            
            # 绝对路径指向其他位置应该被拒绝
            with pytest.raises(SecurityError):
                validate_path_traversal("/etc/passwd")
        finally:
            config.settings.md_root = original_md_root
    
    def test_path_too_long(self, tmp_path):
        """测试超长路径"""
        # 创建测试目录
        test_dir = tmp_path / "docs"
        test_dir.mkdir()
        
        # 临时修改 settings
        from app import config
        original_md_root = config.settings.md_root
        try:
            config.settings.md_root = test_dir
            
            # 超长路径应该被拒绝 - 创建一个真正超长的路径
            long_path = "a" * (MAX_PATH_LENGTH + 1) + ".md"
            with pytest.raises(SecurityError) as exc_info:
                validate_path_traversal(long_path)
            assert "too long" in str(exc_info.value).lower()
        finally:
            config.settings.md_root = original_md_root
    
    def test_nested_valid_path(self, tmp_path):
        """测试嵌套的有效路径"""
        # 创建嵌套目录结构
        test_dir = tmp_path / "docs"
        nested_dir = test_dir / "subdir" / "nested"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "test.md"
        test_file.write_text("test content")
        
        # 临时修改 settings
        from app import config
        original_md_root = config.settings.md_root
        try:
            config.settings.md_root = test_dir
            
            # 嵌套路径应该通过
            result = validate_path_traversal("subdir/nested/test.md")
            assert result.exists()
            assert result.name == "test.md"
        finally:
            config.settings.md_root = original_md_root
