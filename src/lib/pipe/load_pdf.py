import typing as tp
from dataclasses import dataclass
from pathlib import Path

import base64c as base64
from fitz import open as open_pdf  # type: ignore
from PyPDF2 import PdfReader

from ._base import Artifact


@dataclass
class PdfLoader(Artifact):
    def extract_text(self) -> tp.Generator[str, None, None]:  # type: ignore
        text_doc = PdfReader(Path(self.file_path).as_posix())
        for page_number in range(len(text_doc.pages)):
            page = text_doc.pages[page_number]
            yield page.extract_text()

    def extract_image(self):
        img_doc = open_pdf(self.file_path)
        for page in img_doc:  # type: ignore
            for img in page.get_images():  # type: ignore
                xref = img[0]  # type: ignore
                base_image = img_doc.extract_image(xref)  # type: ignore
                image_bytes = base_image["image"]  # type: ignore
                assert isinstance(image_bytes, bytes)
                yield base64.b64encode(image_bytes).decode()
