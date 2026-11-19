import os, tempfile
from pathlib import Path
# 每个测试会话使用独立数据目录，避免上一次运行留下的批次和补正记录串场。
os.environ["DATA_DIR"]=tempfile.mkdtemp(prefix="tidal-window-pytest-")
import pytest
from app.pipeline import run,sample_text
@pytest.fixture
def sample(): return sample_text()
@pytest.fixture
def result(sample): return run(sample)
