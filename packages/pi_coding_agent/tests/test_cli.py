"""Tests for pi_coding_agent CLI."""

from pi_coding_agent.cli.args import VALID_THINKING_LEVELS, is_valid_thinking_level, parse_args


class TestArgParsing:
    """Test CLI argument parsing."""

    def test_parse_empty_args(self):
        args = parse_args([])
        assert args.messages == []
        assert not args.help
        assert not args.version

    def test_parse_help(self):
        args = parse_args(["--help"])
        assert args.help

        args = parse_args(["-h"])
        assert args.help

    def test_parse_version(self):
        args = parse_args(["--version"])
        assert args.version

        args = parse_args(["-v"])
        assert args.version

    def test_parse_message(self):
        args = parse_args(["hello world"])
        assert args.messages == ["hello world"]

    def test_parse_multiple_messages(self):
        args = parse_args(["hello", "world"])
        assert args.messages == ["hello", "world"]

    def test_parse_model(self):
        args = parse_args(["--model", "claude-opus-4-5"])
        assert args.model == "claude-opus-4-5"

    def test_parse_provider(self):
        args = parse_args(["--provider", "anthropic"])
        assert args.provider == "anthropic"

    def test_parse_thinking(self):
        for level in VALID_THINKING_LEVELS:
            args = parse_args(["--thinking", level])
            assert args.thinking == level

    def test_parse_invalid_thinking(self):
        args = parse_args(["--thinking", "invalid"])
        assert args.thinking is None
        assert len(args.diagnostics) == 1
        assert args.diagnostics[0]["type"] == "warning"

    def test_parse_tools(self):
        args = parse_args(["--tools", "read,bash,edit"])
        assert args.tools == ["read", "bash", "edit"]

    def test_parse_tools_with_unknown(self):
        args = parse_args(["--tools", "read,unknown"])
        assert args.tools == ["read"]
        assert len(args.diagnostics) == 1

    def test_parse_no_tools(self):
        args = parse_args(["--no-tools"])
        assert args.no_tools

    def test_parse_file_args(self):
        args = parse_args(["@file1.txt", "@file2.py"])
        assert args.file_args == ["file1.txt", "file2.py"]

    def test_parse_continue(self):
        args = parse_args(["--continue"])
        assert args.continue_

        args = parse_args(["-c"])
        assert args.continue_

    def test_parse_resume(self):
        args = parse_args(["--resume"])
        assert args.resume

        args = parse_args(["-r"])
        assert args.resume

    def test_parse_print(self):
        args = parse_args(["--print"])
        assert args.print_

        args = parse_args(["-p"])
        assert args.print_

    def test_parse_mode(self):
        args = parse_args(["--mode", "json"])
        assert args.mode == "json"

        args = parse_args(["--mode", "rpc"])
        assert args.mode == "rpc"

    def test_parse_verbose(self):
        args = parse_args(["--verbose"])
        assert args.verbose

    def test_parse_offline(self):
        args = parse_args(["--offline"])
        assert args.offline

    def test_parse_unknown_flag(self):
        args = parse_args(["--unknown-flag"])
        assert "unknown-flag" in args.unknown_flags

    def test_parse_unknown_flag_with_value(self):
        args = parse_args(["--custom-opt", "value"])
        assert args.unknown_flags.get("custom-opt") == "value"

    def test_parse_unknown_flag_equals(self):
        args = parse_args(["--key=value"])
        assert args.unknown_flags.get("key") == "value"

    def test_parse_unknown_short_option(self):
        args = parse_args(["-x"])
        assert len(args.diagnostics) == 1
        assert args.diagnostics[0]["type"] == "error"

    def test_parse_list_models(self):
        args = parse_args(["--list-models"])
        assert args.list_models is True

    def test_parse_list_models_with_pattern(self):
        args = parse_args(["--list-models", "claude"])
        assert args.list_models == "claude"


class TestThinkingLevels:
    """Test thinking level validation."""

    def test_valid_thinking_levels(self):
        for level in VALID_THINKING_LEVELS:
            assert is_valid_thinking_level(level)

    def test_invalid_thinking_levels(self):
        assert not is_valid_thinking_level("invalid")
        assert not is_valid_thinking_level("")
        assert not is_valid_thinking_level("HIGH")  # Case sensitive
