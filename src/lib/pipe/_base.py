import typing as tp
from abc import ABC, abstractmethod
from dataclasses import dataclass

import typing_extensions as tpe
from fastapi import UploadFile

MimeType: tpe.TypeAlias = tp.Literal[
    "text/x-c",
    "text/x-c++",
    "text/x-csharp",
    "text/css",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/x-golang",
    "text/html",
    "text/x-java",
    "text/javascript",
    "application/json",
    "text/markdown",
    "application/pdf",
    "text/x-php",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/x-python",
    "text/x-script.python",
    "text/x-ruby",
    "application/x-sh",
    "text/x-tex",
    "application/typescript",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]

FileSuffix: tpe.TypeAlias = tp.Literal[
    ".docx",
    ".pdf",
    ".pptx",
    ".xlsx",
    ".xls",
    ".doc",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".html",
    ".css",
    ".js",
    ".json",
]


def check_suffix(
    file: UploadFile,
) -> FileSuffix:
    if not file.filename and not file.content_type:
        raise ValueError("Invalid file")

    if file.filename:
        if "docx" in file.filename:
            return ".docx"
        if "doc" in file.filename:
            return ".docx"
        if "pdf" in file.filename:
            return ".pdf"
        if "ppt" in file.filename:
            return ".pptx"
        if "pptx" in file.filename:
            return ".pptx"
        if "xlsx" in file.filename:
            return ".xlsx"
        if "xls" in file.filename:
            return ".xlsx"
    if file.content_type:
        if "presentation" in file.content_type:
            return ".pptx"
        if "document" in file.content_type:
            return ".docx"
        if "pdf" in file.content_type:
            return ".pdf"
        if "spreadsheet" in file.content_type:
            return ".xlsx"
    raise ValueError("Invalid file")


@dataclass
class Artifact(ABC):
    file_path: str

    @abstractmethod
    def extract_text(self) -> tp.Generator[str, None, None]:
        pass

    @abstractmethod
    def extract_image(self) -> tp.Generator[str, None, None]:
        pass
