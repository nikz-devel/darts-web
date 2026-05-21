"""
Tests for the JSON logging formatter.
"""

import json
import logging
import unittest

from backend.config.logging import JSONFormatter


class TestJSONFormatter(unittest.TestCase):
    """Unit tests for the structured JSON logging formatter."""

    def setUp(self) -> None:
        self.formatter = JSONFormatter()
        self.logger = logging.getLogger("test_logger")
        self.logger.handlers = []

    def _create_record(
        self,
        level: int = logging.INFO,
        msg: str = "test message",
        exc_info: tuple | None = None,
    ) -> logging.LogRecord:
        return self.logger.makeRecord(
            name="test_logger",
            level=level,
            fn="(test file)",
            lno=1,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )

    def test_formats_basic_message_as_json(self) -> None:
        record = self._create_record(msg="hello world")
        output = self.formatter.format(record)

        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert "timestamp" in parsed

    def test_includes_error_level(self) -> None:
        record = self._create_record(level=logging.ERROR, msg="something failed")
        output = self.formatter.format(record)

        parsed = json.loads(output)
        assert parsed["level"] == "ERROR"

    def test_includes_exception_info(self) -> None:
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = self._create_record(msg="error occurred", exc_info=exc_info)
        output = self.formatter.format(record)

        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_output_is_valid_json(self) -> None:
        record = self._create_record()
        output = self.formatter.format(record)

        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
