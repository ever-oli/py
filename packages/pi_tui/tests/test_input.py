"""Tests for Input component."""

from pi_tui.components.input import Input, KillRing, UndoStack


class TestKillRing:
    """Tests for KillRing class."""

    def test_push_adds_item(self):
        """Push should add item to ring."""
        ring = KillRing()
        ring.push("hello")
        assert len(ring) == 1
        assert ring.peek() == "hello"

    def test_push_empty_does_nothing(self):
        """Push with empty string does nothing."""
        ring = KillRing()
        ring.push("")
        assert len(ring) == 0

    def test_accumulate_appends(self):
        """Accumulate should append to last item."""
        ring = KillRing()
        ring.push("hello")
        ring.push(" world", accumulate=True)
        assert ring.peek() == "hello world"
        assert len(ring) == 1

    def test_accumulate_prepends(self):
        """Accumulate with prepend should prepend."""
        ring = KillRing()
        ring.push("world")
        ring.push("hello ", accumulate=True, prepend=True)
        assert ring.peek() == "hello world"

    def test_rotate_cycles(self):
        """Rotate should move last to first."""
        ring = KillRing()
        ring.push("first")
        ring.push("second")
        ring.push("third")

        assert ring.peek() == "third"
        ring.rotate()
        assert ring.peek() == "second"
        ring.rotate()
        assert ring.peek() == "first"
        ring.rotate()
        assert ring.peek() == "third"

    def test_rotate_single_item(self):
        """Rotate with single item does nothing."""
        ring = KillRing()
        ring.push("only")
        ring.rotate()
        assert ring.peek() == "only"

    def test_peek_empty_returns_none(self):
        """Peek on empty ring returns None."""
        ring = KillRing()
        assert ring.peek() is None


class TestUndoStack:
    """Tests for UndoStack class."""

    def test_push_adds_state(self):
        """Push should add state to stack."""
        stack = UndoStack()
        stack.push({"value": "hello", "cursor": 5})
        assert len(stack) == 1

    def test_pop_returns_state(self):
        """Pop should return most recent state."""
        stack = UndoStack()
        state = {"value": "hello", "cursor": 5}
        stack.push(state)
        result = stack.pop()
        assert result == state

    def test_pop_empty_returns_none(self):
        """Pop on empty stack returns None."""
        stack = UndoStack()
        assert stack.pop() is None

    def test_clear_removes_all(self):
        """Clear should remove all states."""
        stack = UndoStack()
        stack.push({"value": "a"})
        stack.push({"value": "b"})
        stack.clear()
        assert len(stack) == 0

    def test_deep_clone(self):
        """Push should create deep clone."""
        stack = UndoStack()
        original = {"value": "hello", "nested": {"a": 1}}
        stack.push(original)

        # Modify original
        original["nested"]["a"] = 2

        # Pop should have original values
        result = stack.pop()
        assert result["nested"]["a"] == 1


class TestInput:
    """Tests for Input component."""

    def test_get_value_returns_current(self):
        """get_value should return current value."""
        input_comp = Input()
        assert input_comp.get_value() == ""

    def test_set_value_updates(self):
        """set_value should update value and cursor."""
        input_comp = Input()
        input_comp.set_value("hello")
        assert input_comp.get_value() == "hello"

    def test_clear_resets(self):
        """Clear should reset state."""
        input_comp = Input()
        input_comp.set_value("hello")
        input_comp.clear()
        assert input_comp.get_value() == ""
        assert input_comp.is_empty()

    def test_insert_characters(self):
        """Should insert characters at cursor."""
        input_comp = Input()
        input_comp._insert_characters("hello")
        assert input_comp.get_value() == "hello"

    def test_backspace_deletes_previous(self):
        """Backspace should delete previous character."""
        input_comp = Input()
        input_comp._insert_characters("hello")
        input_comp._handle_backspace()
        assert input_comp.get_value() == "hell"

    def test_backspace_at_start_does_nothing(self):
        """Backspace at start should do nothing."""
        input_comp = Input()
        input_comp._handle_backspace()
        assert input_comp.get_value() == ""

    def test_forward_delete_deletes_next(self):
        """Forward delete should delete next character."""
        input_comp = Input()
        input_comp._insert_characters("hello")
        input_comp._cursor_pos = 0
        input_comp._handle_forward_delete()
        assert input_comp.get_value() == "ello"

    def test_delete_word_backwards(self):
        """Delete word backwards should remove word."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 11
        input_comp._delete_word_backwards()
        assert input_comp.get_value() == "hello "

    def test_delete_word_forwards(self):
        """Delete word forwards should remove word."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 0
        input_comp._delete_word_forwards()
        assert input_comp.get_value() == "world"

    def test_delete_to_end(self):
        """Delete to end should remove from cursor to end."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 5
        input_comp._delete_to_end_of_line()
        assert input_comp.get_value() == "hello"

    def test_delete_to_start(self):
        """Delete to start should remove from start to cursor."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 6
        input_comp._delete_to_start_of_line()
        assert input_comp.get_value() == "world"

    def test_yank_from_kill_ring(self):
        """Yank should paste from kill ring."""
        input_comp = Input()
        input_comp._kill_ring.push("hello")
        input_comp._yank()
        assert input_comp.get_value() == "hello"

    def test_yank_empty_ring(self):
        """Yank with empty ring should do nothing."""
        input_comp = Input()
        input_comp._yank()
        assert input_comp.get_value() == ""

    def test_yank_pop_cycles(self):
        """Yank pop should cycle through kill ring."""
        input_comp = Input()
        input_comp._kill_ring.push("first")
        input_comp._kill_ring.push("second")
        input_comp._kill_ring.push("third")

        input_comp._yank()  # First yank - "third"
        assert input_comp.get_value() == "third"
        assert input_comp._cursor_pos == len("third")

        input_comp._yank_pop()  # Pop to "second"
        assert input_comp.get_value() == "second"

    def test_history_navigation(self):
        """Should navigate through history."""
        input_comp = Input()
        # History is stored with most recent first (index 0)
        # _history_index = -1 means "before history" (user's current input)
        input_comp.add_to_history("first")
        input_comp.add_to_history("second")

        # Navigate "up" to see more recent history (direction 1 in this implementation)
        input_comp._navigate_history(1)
        assert input_comp.get_value() == "second"

        input_comp._navigate_history(1)
        assert input_comp.get_value() == "first"

    def test_render_returns_single_line(self):
        """Render should return single line."""
        input_comp = Input()
        input_comp._insert_characters("hello")
        lines = input_comp.render(80)
        assert len(lines) == 1
        assert "hello" in lines[0]

    def test_add_to_history_avoids_duplicates(self):
        """Should avoid consecutive duplicates in history."""
        input_comp = Input()
        input_comp.add_to_history("test")
        input_comp.add_to_history("test")
        input_comp.add_to_history("test")

        # Should only have one entry
        assert len(input_comp._history) == 1

    def test_cursor_movement(self):
        """Should move cursor correctly."""
        input_comp = Input()
        input_comp._insert_characters("hello")
        assert input_comp._cursor_pos == 5

        input_comp._move_cursor(-1)
        assert input_comp._cursor_pos == 4

        input_comp._move_to_start()
        assert input_comp._cursor_pos == 0

        input_comp._move_to_end()
        assert input_comp._cursor_pos == 5

    def test_word_movement(self):
        """Should move by words."""
        input_comp = Input()
        input_comp._insert_characters("hello world")

        input_comp._move_to_end()
        input_comp._move_word_backwards()
        # Cursor should be at start of "world" or end of "hello "

        input_comp._move_word_forwards()
        # Cursor should be at end


class TestInputKillRingIntegration:
    """Tests for kill ring integration with input."""

    def test_delete_word_saves_to_ring(self):
        """Delete word should save to kill ring."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 11

        input_comp._delete_word_backwards()
        assert input_comp._kill_ring.peek() == "world"

    def test_delete_to_end_saves_to_ring(self):
        """Delete to end should save to kill ring."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 6

        input_comp._delete_to_end_of_line()
        assert input_comp._kill_ring.peek() == "world"

    def test_delete_to_start_saves_to_ring(self):
        """Delete to start should save to kill ring."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 5

        input_comp._delete_to_start_of_line()
        assert input_comp._kill_ring.peek() == "hello"

    def test_consecutive_kills_accumulate(self):
        """Consecutive kills should accumulate."""
        input_comp = Input()
        input_comp._insert_characters("one two three")
        input_comp._cursor_pos = 13

        # Three consecutive kills
        input_comp._delete_word_backwards()  # "three"
        input_comp._delete_word_backwards()  # " two"
        input_comp._delete_word_backwards()  # "one "

        # Should have accumulated into single entry
        assert input_comp._kill_ring.peek() == "one two three"

    def test_non_delete_breaks_accumulation(self):
        """Non-delete action should break kill accumulation."""
        input_comp = Input()
        input_comp._insert_characters("hello world")
        input_comp._cursor_pos = 5

        input_comp._delete_word_backwards()
        assert input_comp._kill_ring.peek() == "hello"

        # Type something to break accumulation
        input_comp._insert_characters("x")

        input_comp._delete_word_backwards()
        assert input_comp._kill_ring.peek() == "x"
