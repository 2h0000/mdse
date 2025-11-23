"""配置管理测试

测试配置验证和错误处理功能。
验证需求: 7.1, 7.2, 7.3, 7.5
"""

import os
import pytest
import tempfile
from pathlib import Path
from pydantic import ValidationError

from app.config import Settings, ConfigurationError


class TestConfigValidation:
    """配置验证测试类
    
    验证需求: 7.3 - 配置的路径不存在时记录错误并拒绝启动
    验证需求: 7.5 - 配置文件格式错误时提供清晰的错误信息
    """
    
    def test_valid_config(self, tmp_path):
        """测试有效配置能够成功加载"""
        # 创建临时目录
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        db_path = db_dir / "test.db"
        
        # 创建配置
        settings = Settings(
            md_root=md_root,
            db_path=db_path,
            log_level="INFO"
        )
        
        assert settings.md_root == md_root
        assert settings.db_path == db_path
        assert settings.log_level == "INFO"
    
    def test_md_root_not_exists(self, tmp_path):
        """测试 MD_ROOT 不存在时抛出错误
        
        验证需求: 7.3
        """
        non_existent_path = tmp_path / "non_existent"
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=non_existent_path,
                db_path=db_dir / "test.db"
            )
        
        # 验证错误信息包含路径信息
        error_msg = str(exc_info.value)
        assert "不存在" in error_msg or "does not exist" in error_msg.lower()
    
    def test_md_root_is_file(self, tmp_path):
        """测试 MD_ROOT 是文件而非目录时抛出错误
        
        验证需求: 7.3
        """
        # 创建一个文件而不是目录
        md_file = tmp_path / "file.txt"
        md_file.write_text("test")
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_file,
                db_path=db_dir / "test.db"
            )
        
        error_msg = str(exc_info.value)
        assert "目录" in error_msg or "directory" in error_msg.lower()
    
    def test_db_path_parent_not_exists(self, tmp_path):
        """测试数据库父目录不存在时抛出错误
        
        验证需求: 7.3
        """
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        # 数据库路径的父目录不存在
        non_existent_dir = tmp_path / "non_existent"
        db_path = non_existent_dir / "test.db"
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_path
            )
        
        error_msg = str(exc_info.value)
        assert "不存在" in error_msg or "does not exist" in error_msg.lower()
    
    def test_invalid_log_level(self, tmp_path):
        """测试无效的日志级别抛出错误
        
        验证需求: 7.5
        """
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_dir / "test.db",
                log_level="INVALID"
            )
        
        error_msg = str(exc_info.value)
        assert "无效" in error_msg or "invalid" in error_msg.lower()
    
    def test_log_level_case_insensitive(self, tmp_path):
        """测试日志级别不区分大小写"""
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        # 小写应该被转换为大写
        settings = Settings(
            md_root=md_root,
            db_path=db_dir / "test.db",
            log_level="info"
        )
        
        assert settings.log_level == "INFO"
    
    def test_max_search_limit_validation(self, tmp_path):
        """测试最大搜索限制验证
        
        验证需求: 7.5
        """
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        # 测试负数
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_dir / "test.db",
                max_search_limit=-1
            )
        assert "大于 0" in str(exc_info.value) or "greater than 0" in str(exc_info.value).lower()
        
        # 测试过大的值
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_dir / "test.db",
                max_search_limit=2000
            )
        assert "1000" in str(exc_info.value)
    
    def test_snippet_tokens_validation(self, tmp_path):
        """测试摘要 token 数量验证
        
        验证需求: 7.5
        """
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        # 测试负数
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_dir / "test.db",
                snippet_tokens=0
            )
        assert "大于 0" in str(exc_info.value) or "greater than 0" in str(exc_info.value).lower()
        
        # 测试过大的值
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                md_root=md_root,
                db_path=db_dir / "test.db",
                snippet_tokens=200
            )
        assert "100" in str(exc_info.value)
    
    def test_default_values(self, tmp_path):
        """测试默认配置值"""
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        # 只提供必需的配置
        settings = Settings(md_root=md_root)
        
        # 验证默认值
        assert settings.log_level == "INFO"
        assert settings.default_limit == 20
        assert settings.max_search_limit == 100
        assert settings.snippet_tokens == 10
        assert settings.watch_recursive is True
        assert settings.fts_tokenizer == "unicode61 remove_diacritics 1"


class TestConfigFileLoading:
    """配置文件加载测试类
    
    测试从配置文件（.env）读取配置参数。
    验证需求: 7.1, 7.2
    """
    
    def test_load_md_root_from_env_file(self, tmp_path, monkeypatch):
        """测试从配置文件读取 MD_ROOT
        
        验证需求: 7.1 - 系统启动时从配置文件读取 Markdown 文档根目录路径
        """
        # 创建临时目录结构
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        # 创建 .env 文件
        env_file = tmp_path / ".env"
        env_content = f"""MD_ROOT={md_root}
DB_PATH={db_dir / "test.db"}
"""
        env_file.write_text(env_content, encoding='utf-8')
        
        # 切换到临时目录以便 Settings 能找到 .env 文件
        monkeypatch.chdir(tmp_path)
        
        # 加载配置
        settings = Settings()
        
        # 验证 MD_ROOT 从配置文件正确读取
        assert settings.md_root == md_root
        assert settings.md_root.exists()
        assert settings.md_root.is_dir()
    
    def test_load_db_path_from_env_file(self, tmp_path, monkeypatch):
        """测试从配置文件读取 DB_PATH
        
        验证需求: 7.2 - 系统启动时从配置文件读取数据库文件路径
        """
        # 创建临时目录结构
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "database"
        db_dir.mkdir()
        db_path = db_dir / "custom_search.db"
        
        # 创建 .env 文件
        env_file = tmp_path / ".env"
        env_content = f"""MD_ROOT={md_root}
DB_PATH={db_path}
"""
        env_file.write_text(env_content, encoding='utf-8')
        
        # 切换到临时目录以便 Settings 能找到 .env 文件
        monkeypatch.chdir(tmp_path)
        
        # 加载配置
        settings = Settings()
        
        # 验证 DB_PATH 从配置文件正确读取
        assert settings.db_path == db_path
        assert settings.db_path.parent.exists()
    
    def test_load_both_paths_from_env_file(self, tmp_path, monkeypatch):
        """测试同时从配置文件读取 MD_ROOT 和 DB_PATH
        
        验证需求: 7.1, 7.2
        """
        # 创建临时目录结构
        md_root = tmp_path / "markdown_files"
        md_root.mkdir()
        
        db_dir = tmp_path / "db_storage"
        db_dir.mkdir()
        db_path = db_dir / "md_search.db"
        
        # 创建 .env 文件，包含两个配置项
        env_file = tmp_path / ".env"
        env_content = f"""# Configuration file
MD_ROOT={md_root}
DB_PATH={db_path}
LOG_LEVEL=DEBUG
"""
        env_file.write_text(env_content, encoding='utf-8')
        
        # 切换到临时目录
        monkeypatch.chdir(tmp_path)
        
        # 加载配置
        settings = Settings()
        
        # 验证两个路径都正确读取
        assert settings.md_root == md_root
        assert settings.db_path == db_path
        assert settings.log_level == "DEBUG"
    
    def test_env_file_with_relative_paths(self, tmp_path, monkeypatch):
        """测试配置文件中使用相对路径
        
        验证需求: 7.1, 7.2
        """
        # 创建临时目录结构
        md_root = tmp_path / "docs"
        md_root.mkdir()
        
        db_dir = tmp_path / "data"
        db_dir.mkdir()
        
        # 创建 .env 文件，使用相对路径
        env_file = tmp_path / ".env"
        env_content = """MD_ROOT=./docs
DB_PATH=./data/md_search.db
"""
        env_file.write_text(env_content, encoding='utf-8')
        
        # 切换到临时目录
        monkeypatch.chdir(tmp_path)
        
        # 加载配置
        settings = Settings()
        
        # 验证相对路径被正确解析
        assert settings.md_root.name == "docs"
        assert settings.md_root.exists()
        assert settings.db_path.name == "md_search.db"
        assert settings.db_path.parent.name == "data"
    
    def test_env_file_missing_md_root(self, tmp_path, monkeypatch):
        """测试配置文件缺少必需的 MD_ROOT 参数
        
        验证需求: 7.1
        """
        # 创建只包含 DB_PATH 的 .env 文件
        env_file = tmp_path / ".env"
        env_content = """DB_PATH=./data/test.db
"""
        env_file.write_text(env_content, encoding='utf-8')
        
        # 切换到临时目录
        monkeypatch.chdir(tmp_path)
        
        # 尝试加载配置应该失败，因为 MD_ROOT 是必需的
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        # 验证错误信息提到缺少字段
        error_msg = str(exc_info.value)
        assert "md_root" in error_msg.lower() or "field required" in error_msg.lower()
