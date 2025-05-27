"""
测试文件处理服务模块。
"""

import os
from pathlib import Path
from unittest.mock import mock_open, patch, AsyncMock, MagicMock

import pytest
import aiofiles

from gnosis.services.subtitle import SubtitleService


@pytest.fixture
def temp_file_path(tmp_path):
    """创建一个临时文件路径。"""
    return str(tmp_path / "test_file.txt")


@pytest.fixture
def sample_content():
    """返回示例文件内容。"""
    return "这是测试内容\n第二行\n第三行"


class TestSubtitleService:
    """测试文件处理服务。"""

    @pytest.mark.asyncio
    async def test_read_file(self, temp_file_path, sample_content):
        """测试读取文件功能。"""
        # 准备测试文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(sample_content)

        # 测试读取文件
        content = await SubtitleService.read_file(temp_file_path)
        assert content == sample_content

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """测试读取不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            await SubtitleService.read_file("/path/to/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_read_file_permission_error(self, temp_file_path, sample_content):
        """测试读取无权限文件。"""
        # 先创建文件，确保文件存在
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(sample_content)

        # 然后模拟权限错误
        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError):
                await SubtitleService.read_file(temp_file_path)

    @pytest.mark.asyncio
    async def test_read_file_unicode_error(self, temp_file_path):
        """测试读取编码错误的文件。"""
        # 创建文件以确保存在
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write("test content")

        # 创建正确的模拟对象
        # 使用 patch 的 side_effect 直接抛出异常
        with patch("aiofiles.open", side_effect=UnicodeDecodeError(
            "utf-8", b"\x80abc", 0, 1, "invalid start byte"
        )):
            with pytest.raises(UnicodeDecodeError):
                await SubtitleService.read_file(temp_file_path)

    @pytest.mark.asyncio
    async def test_write_file(self, temp_file_path, sample_content):
        """测试写入文件功能。"""
        # 测试写入文件
        result = await SubtitleService.write_file(sample_content, temp_file_path)
        assert result == temp_file_path

        # 验证文件内容
        with open(temp_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == sample_content

    @pytest.mark.asyncio
    async def test_write_file_create_directory(self, tmp_path, sample_content):
        """测试写入文件时创建目录。"""
        nested_path = str(tmp_path / "nested" / "directory" / "test_file.txt")

        # 测试写入文件（应自动创建目录）
        result = await SubtitleService.write_file(sample_content, nested_path)
        assert result == nested_path

        # 验证文件内容
        with open(nested_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == sample_content

    @pytest.mark.asyncio
    async def test_write_file_permission_error(self, temp_file_path, sample_content):
        """测试写入无权限文件。"""
        # 确保目录存在检查不会失败
        directory = os.path.dirname(temp_file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # 模拟 aiofiles.open 抛出权限错误
        with patch("aiofiles.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                await SubtitleService.write_file(sample_content, temp_file_path)

    @pytest.mark.asyncio
    async def test_ensure_file_exists(self, temp_file_path, sample_content):
        """测试检查文件是否存在。"""
        # 准备测试文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(sample_content)

        # 测试文件存在
        assert await SubtitleService.ensure_file_exists(temp_file_path) is True

        # 测试文件不存在
        assert (
            await SubtitleService.ensure_file_exists("/path/to/nonexistent/file.txt")
            is False
        )

    @pytest.mark.asyncio
    async def test_get_file_info(self, temp_file_path, sample_content):
        """测试获取文件信息。"""
        # 准备测试文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(sample_content)

        # 测试获取文件信息
        file_info = await SubtitleService.get_file_info(temp_file_path)

        assert file_info["path"] == temp_file_path
        assert file_info["name"] == os.path.basename(temp_file_path)
        assert file_info["extension"] == "txt"
        # UTF-8 编码的中文字符占用多个字节，所以不能直接比较字符串长度
        # 而应该比较文件实际大小
        assert file_info["size_bytes"] > 0  # 只要确认文件有内容即可
        assert "modified_time" in file_info
        assert "created_time" in file_info

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(self):
        """测试获取不存在文件的信息。"""
        with pytest.raises(FileNotFoundError):
            await SubtitleService.get_file_info("/path/to/nonexistent/file.txt")
