"""
pytest 配置文件，用于设置测试环境。
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from gnosis.services.subtitle.parser import Subtitle

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_file_path(tmp_path):
    """创建一个临时文件路径。"""
    return str(tmp_path / "test_file.srt")


@pytest.fixture
def sample_srt_content():
    """返回示例SRT文件内容。"""
    return """1
00:00:01,000 --> 00:00:04,000
Hello world!

2
00:00:05,000 --> 00:00:08,000
This is a test
of subtitle formatting.

3
00:00:10,000 --> 00:00:15,000
Another subtitle line.
"""


@pytest.fixture
def sample_subtitles():
    """返回示例Subtitle对象列表。"""
    return [
        Subtitle(
            index=1,
            start=timedelta(seconds=1),
            end=timedelta(seconds=4),
            content="Hello world!",
        ),
        Subtitle(
            index=2,
            start=timedelta(seconds=5),
            end=timedelta(seconds=8),
            content="This is a test\nof subtitle formatting.",
        ),
        Subtitle(
            index=3,
            start=timedelta(seconds=10),
            end=timedelta(seconds=15),
            content="Another subtitle line.",
        ),
    ]
