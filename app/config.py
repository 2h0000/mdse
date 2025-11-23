"""配置管理模块

提供全局配置参数，支持从环境变量和 .env 文件读取配置。
包含配置验证和错误提示功能。
验证需求: 7.1, 7.2, 7.3, 7.5
"""

import sys
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator, ValidationError


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """配置错误异常类
    
    用于表示配置验证失败的情况。
    验证需求: 7.5
    """
    pass


class Settings(BaseSettings):
    """应用配置类
    
    从环境变量或 .env 文件读取配置参数。
    包含路径存在性验证。
    验证需求: 7.1, 7.2, 7.3
    """
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    # Markdown 文档根目录 (需求 7.1)
    md_root: Path
    
    # SQLite 数据库路径 (需求 7.2)
    db_path: Path = Path("./data/md_search.db")
    
    # 日志级别
    log_level: str = "INFO"
    
    # FTS5 分词器配置
    fts_tokenizer: str = "unicode61 remove_diacritics 1"
    
    # 搜索配置
    default_limit: int = 20
    max_search_limit: int = 100
    snippet_tokens: int = 10
    
    # 监听器配置
    watch_recursive: bool = True
    
    @field_validator('md_root')
    @classmethod
    def validate_md_root(cls, v: Path) -> Path:
        """验证 Markdown 文档根目录是否存在
        
        验证需求: 7.3 - 配置的路径不存在时记录错误并拒绝启动
        """
        if not v.exists():
            raise ValueError(
                f"Markdown 文档根目录不存在: {v.absolute()}\n"
                f"请确保路径正确，或创建该目录。"
            )
        if not v.is_dir():
            raise ValueError(
                f"MD_ROOT 必须是一个目录，但 {v.absolute()} 是一个文件。"
            )
        return v
    
    @field_validator('db_path')
    @classmethod
    def validate_db_path(cls, v: Path) -> Path:
        """验证数据库路径的父目录是否存在
        
        验证需求: 7.3 - 配置的路径不存在时记录错误并拒绝启动
        """
        # 数据库文件本身可以不存在（会自动创建），但父目录必须存在
        parent_dir = v.parent
        if not parent_dir.exists():
            raise ValueError(
                f"数据库文件的父目录不存在: {parent_dir.absolute()}\n"
                f"请创建目录: mkdir -p {parent_dir}"
            )
        return v
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别是否有效
        
        验证需求: 7.5 - 配置文件格式错误时提供清晰的错误信息
        """
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"无效的日志级别: {v}\n"
                f"有效的日志级别: {', '.join(valid_levels)}"
            )
        return v_upper
    
    @field_validator('max_search_limit')
    @classmethod
    def validate_max_search_limit(cls, v: int) -> int:
        """验证最大搜索限制是否合理
        
        验证需求: 7.5 - 配置文件格式错误时提供清晰的错误信息
        """
        if v <= 0:
            raise ValueError(
                f"MAX_SEARCH_LIMIT 必须大于 0，当前值: {v}"
            )
        if v > 1000:
            raise ValueError(
                f"MAX_SEARCH_LIMIT 不应超过 1000，当前值: {v}\n"
                f"过大的限制可能导致性能问题。"
            )
        return v
    
    @field_validator('snippet_tokens')
    @classmethod
    def validate_snippet_tokens(cls, v: int) -> int:
        """验证摘要 token 数量是否合理
        
        验证需求: 7.5 - 配置文件格式错误时提供清晰的错误信息
        """
        if v <= 0:
            raise ValueError(
                f"SNIPPET_TOKENS 必须大于 0，当前值: {v}"
            )
        if v > 100:
            raise ValueError(
                f"SNIPPET_TOKENS 不应超过 100，当前值: {v}\n"
                f"过大的值可能导致摘要过长。"
            )
        return v


def load_settings() -> Settings:
    """加载并验证配置
    
    如果配置验证失败，记录错误并退出程序。
    验证需求: 7.3, 7.5
    
    Returns:
        Settings: 验证通过的配置实例
        
    Raises:
        SystemExit: 配置验证失败时退出
    """
    try:
        return Settings()
    except ValidationError as e:
        # 格式化错误信息
        error_messages = []
        error_messages.append("=" * 60)
        error_messages.append("配置错误 - 应用无法启动")
        error_messages.append("=" * 60)
        
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            msg = error['msg']
            error_messages.append(f"\n字段: {field.upper()}")
            error_messages.append(f"错误: {msg}")
        
        error_messages.append("\n" + "=" * 60)
        error_messages.append("请检查 .env 文件或环境变量配置。")
        error_messages.append("参考 .env.example 文件了解正确的配置格式。")
        error_messages.append("=" * 60)
        
        error_text = "\n".join(error_messages)
        logger.error(error_text)
        print(error_text, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_text = (
            f"加载配置时发生未预期的错误: {str(e)}\n"
            f"请检查配置文件格式是否正确。"
        )
        logger.error(error_text)
        print(error_text, file=sys.stderr)
        sys.exit(1)


# 全局配置实例
# 使用 load_settings() 确保配置验证
settings = load_settings()
