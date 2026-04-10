"""Tests for pi_coding_agent tools."""

import tempfile
from pathlib import Path

import pytest
from pi_coding_agent.tools import (
    create_bash_tool,
    create_coding_tools,
    create_edit_tool,
    create_find_tool,
    create_grep_tool,
    create_ls_tool,
    create_read_only_tools,
    create_read_tool,
    create_write_tool,
    truncate_head,
    truncate_tail,
)


class TestTruncate:
    """Test truncation utilities."""

    def test_truncate_head_no_truncation_needed(self):
        content = "line1\nline2\nline3"
        result = truncate_head(content, max_lines=10, max_bytes=1024)
        assert result.content == content
        assert not result.truncated
        assert result.total_lines == 3
        assert result.output_lines == 3

    def test_truncate_head_by_lines(self):
        content = "\n".join([f"line{i}" for i in range(100)])
        result = truncate_head(content, max_lines=10, max_bytes=10000)
        assert result.truncated
        assert result.truncated_by == "lines"
        assert result.output_lines == 10

    def test_truncate_head_by_bytes(self):
        content = "x" * 1000
        result = truncate_head(content, max_lines=100, max_bytes=100)
        assert result.truncated
        assert result.truncated_by == "bytes"
        # When first line exceeds limit, it's marked as first_line_exceeds_limit
        assert result.first_line_exceeds_limit
        assert result.output_lines == 1

    def test_truncate_tail(self):
        content = "\n".join([f"line{i}" for i in range(100)])
        result = truncate_tail(content, max_lines=10, max_bytes=10000)
        assert result.truncated
        assert result.output_lines == 10
        assert "line90" in result.content
        assert "line0" not in result.content

    def test_truncate_empty_content(self):
        result = truncate_head("")
        assert result.content == ""
        assert not result.truncated


class TestReadTool:
    """Test read tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    def test_file(self, temp_dir):
        path = Path(temp_dir) / "test.txt"
        path.write_text("line1\nline2\nline3\n")
        return str(path)

    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir, test_file):
        tool = create_read_tool(temp_dir)
        result = await tool["execute"](path="test.txt")

        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "line1" in result["content"][0]["text"]
        assert "line2" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_read_with_offset(self, temp_dir, test_file):
        tool = create_read_tool(temp_dir)
        result = await tool["execute"](path="test.txt", offset=2)

        content = result["content"][0]["text"]
        assert "line1" not in content
        assert "line2" in content

    @pytest.mark.asyncio
    async def test_read_with_limit(self, temp_dir, test_file):
        tool = create_read_tool(temp_dir)
        result = await tool["execute"](path="test.txt", limit=1)

        content = result["content"][0]["text"]
        assert "line1" in content
        assert "line2" not in content


class TestWriteTool:
    """Test write tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        tool = create_write_tool(temp_dir)
        result = await tool["execute"](path="output.txt", content="Hello, World!")

        assert "success" in result["content"][0]["text"].lower()

        written = Path(temp_dir) / "output.txt"
        assert written.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_creates_directories(self, temp_dir):
        tool = create_write_tool(temp_dir)
        await tool["execute"](path="subdir/nested/file.txt", content="nested content")

        written = Path(temp_dir) / "subdir" / "nested" / "file.txt"
        assert written.read_text() == "nested content"


class TestEditTool:
    """Test edit tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.fixture
    def test_file(self, temp_dir):
        path = Path(temp_dir) / "test.txt"
        path.write_text("Hello, World!\nThis is a test.\n")
        return str(path)

    @pytest.mark.asyncio
    async def test_edit_file(self, temp_dir, test_file):
        tool = create_edit_tool(temp_dir)
        result = await tool["execute"](
            path="test.txt",
            edits=[{"oldText": "Hello, World!", "newText": "Hi, Universe!"}],
        )

        assert "success" in result["content"][0]["text"].lower()

        edited = Path(test_file)
        content = edited.read_text()
        assert "Hi, Universe!" in content
        assert "Hello, World!" not in content

    @pytest.mark.asyncio
    async def test_edit_multiple(self, temp_dir, test_file):
        tool = create_edit_tool(temp_dir)
        await tool["execute"](
            path="test.txt",
            edits=[
                {"oldText": "Hello", "newText": "Hi"},
                {"oldText": "test", "newText": "example"},
            ],
        )

        edited = Path(test_file)
        content = edited.read_text()
        assert "Hi" in content
        assert "example" in content


class TestBashTool:
    """Test bash tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    @pytest.mark.asyncio
    async def test_execute_command(self, temp_dir):
        tool = create_bash_tool(temp_dir)
        result = await tool["execute"](command="echo Hello")

        assert "Hello" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_exit_code(self, temp_dir):
        tool = create_bash_tool(temp_dir)
        result = await tool["execute"](command="exit 1")

        assert "exit code: 1" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_timeout(self, temp_dir):
        tool = create_bash_tool(temp_dir)

        with pytest.raises(RuntimeError, match="timeout"):
            await tool["execute"](command="sleep 10", timeout=0.1)


class TestGrepTool:
    """Test grep tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create test files
            (Path(tmp) / "file1.py").write_text("def hello():\n    pass\n")
            (Path(tmp) / "file2.py").write_text("def world():\n    pass\n")
            (Path(tmp) / "readme.txt").write_text("Hello world\n")
            yield tmp

    @pytest.mark.asyncio
    async def test_grep_pattern(self, temp_dir):
        tool = create_grep_tool(temp_dir)
        result = await tool["execute"](pattern="def")

        content = result["content"][0]["text"]
        assert "file1.py" in content
        assert "file2.py" in content

    @pytest.mark.asyncio
    async def test_grep_case_insensitive(self, temp_dir):
        tool = create_grep_tool(temp_dir)
        result = await tool["execute"](pattern="HELLO")

        content = result["content"][0]["text"]
        # Should find "Hello" despite case difference
        assert "readme.txt" in content


class TestFindTool:
    """Test find tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test1.py").write_text("# test")
            (Path(tmp) / "test2.py").write_text("# test")
            (Path(tmp) / "other.txt").write_text("text")
            yield tmp

    @pytest.mark.asyncio
    async def test_find_by_pattern(self, temp_dir):
        tool = create_find_tool(temp_dir)
        result = await tool["execute"](name_pattern="*.py")

        content = result["content"][0]["text"]
        assert "test1.py" in content
        assert "test2.py" in content
        assert "other.txt" not in content


class TestLsTool:
    """Test ls tool."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "file.txt").write_text("content")
            (Path(tmp) / "subdir").mkdir()
            yield tmp

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_dir):
        tool = create_ls_tool(temp_dir)
        result = await tool["execute"]()

        content = result["content"][0]["text"]
        assert "file.txt" in content
        assert "subdir" in content

    @pytest.mark.asyncio
    async def test_list_specific_path(self, temp_dir):
        tool = create_ls_tool(temp_dir)
        result = await tool["execute"](path="subdir")

        content = result["content"][0]["text"]
        assert "empty" in content.lower() or "directory" in content.lower()


class TestToolFactory:
    """Test tool factory functions."""

    def test_create_coding_tools(self):
        tools = create_coding_tools("/tmp")
        names = [t["name"] for t in tools]
        assert "read" in names
        assert "bash" in names
        assert "edit" in names
        assert "write" in names

    def test_create_read_only_tools(self):
        tools = create_read_only_tools("/tmp")
        names = [t["name"] for t in tools]
        assert "read" in names
        assert "grep" in names
        assert "find" in names
        assert "ls" in names
        assert "bash" not in names
        assert "edit" not in names
        assert "write" not in names
