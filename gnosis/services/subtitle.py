"""
文本文件处理服务，提供基本的文件读写功能。
"""

import os
from typing import Any, Dict


class SubtitleService:
    """文本文件处理服务类，提供基本的文件读写功能。"""

    @staticmethod
    async def read_file(file_path: str, encoding: str = "utf-8") -> str:
        """读取文本文件的内容。

        Args:
            file_path: 文件路径
            encoding: 文件编码，默认为 UTF-8

        Returns:
            str: 文件内容

        Raises:
            FileNotFoundError: 如果文件不存在
            PermissionError: 如果没有权限读取文件
            UnicodeDecodeError: 如果文件编码不匹配
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"没有权限读取文件: {file_path}")

        try:
            # 读取文件内容
            with open(file_path, "r", encoding=encoding) as file:
                content = file.read()
                return content
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                f"文件编码错误: {e}", e.object, e.start, e.end, e.reason
            )
        except Exception as e:
            raise

    @staticmethod
    async def write_file(content: str, file_path: str, encoding: str = "utf-8") -> str:
        """将内容写入文本文件。

        Args:
            content: 要写入的文本内容
            file_path: 目标文件路径
            encoding: 文件编码，默认为 UTF-8

        Returns:
            str: 写入的文件路径

        Raises:
            PermissionError: 如果没有权限写入文件
            OSError: 如果目录不存在或无法创建
        """
        # 确保目标目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                raise OSError(f"无法创建目录: {e}")

        try:
            # 写入文件内容
            with open(file_path, "w", encoding=encoding) as file:
                file.write(content)
                return file_path
        except PermissionError as e:
            raise PermissionError(f"没有权限写入文件: {e}")
        except Exception as e:
            raise

    @staticmethod
    async def ensure_file_exists(file_path: str) -> bool:
        """检查文件是否存在。

        Args:
            file_path: 要检查的文件路径

        Returns:
            bool: 如果文件存在则返回 True，否则返回 False
        """
        return os.path.exists(file_path)

    @staticmethod
    async def get_file_info(file_path: str) -> Dict[str, Any]:
        """获取文件的基本信息。

        Args:
            file_path: 文件路径

        Returns:
            Dict[str, Any]: 包含文件信息的字典，包括大小、修改时间等

        Raises:
            FileNotFoundError: 如果文件不存在
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        file_stat = os.stat(file_path)
        file_info = {
            "path": file_path,
            "name": os.path.basename(file_path),
            "extension": os.path.splitext(file_path)[1].lower().lstrip("."),
            "size_bytes": file_stat.st_size,
            "modified_time": file_stat.st_mtime,
            "created_time": file_stat.st_ctime,
        }

        return file_info
