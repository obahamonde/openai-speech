import re
from dataclasses import dataclass

import base64c as base64  # type: ignore

from ._base import Artifact


@dataclass
class MarkdownLoader(Artifact):

    def extract_text(self):
        for line in self.file_path:
            for match in re.match(r"!\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)", line):
                yield match
    def extract_image(self):
        for line in self.file_path:
            if isinstance(line, bytes):
                yield base64.b64encode(line).decode()
