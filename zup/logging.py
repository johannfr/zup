import logging
import re


class RedactingFormatter(logging.Formatter):
    def __init__(self, redact_patterns=[], **kwargs):
        super().__init__(**kwargs)
        self.redact_patterns = redact_patterns

    def format(self, record):
        message = super().format(record)
        for pattern, replacement in self.redact_patterns:
            message = re.sub(pattern, replacement, message)
        return message
