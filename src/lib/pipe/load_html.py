import typing as tp

from contextlib import contextmanager
from dataclasses import dataclass

from bs4 import BeautifulSoup, CData, NavigableString
from requests import Session
from openai._utils._proxy import LazyProxy
import base64c as base64  # type: ignore

from ._base import Artifact

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class HTMLoader(Artifact, LazyProxy[Session]):
    def extract_text(self):
        with self.__load__() as session:
            response = session.get(self.file_path, headers=HEADERS)
            soup = BeautifulSoup(response.text, "lxml")
            for paragraph in soup.get_text(
                separator="\n", strip=True, types=(NavigableString, CData)
            ):
                yield paragraph

    def __load__(self):
        s = Session()
        s.headers.update(HEADERS)
        return s

    def _extract_image(self, *, src: str):
        if self.file_path.startswith("http"):
            with self.__load__() as session:
                with open(self.file_path, "rb") as file:
                    try:
                        response = session.get(self.file_path, headers=HEADERS)
                        soup = BeautifulSoup(response.text, "lxml")
                        for image in soup.find_all("img"):
                            src = image.get("src")
                            if src and src.startswith("data:"):
                                yield src
                            elif src and src.startswith("http"):
                                content = session.get(src).content
                                yield base64.b64encode(content).decode("utf-8")
                            else:
                                yield base64.b64encode(file.read()).decode("utf-8")
                    except Exception as e:
                        raise e
                    finally:
                        file.close()
                        session.close()
        else:
            with open(self.file_path, "rb") as file:
                yield base64.b64encode(file.read()).decode("utf-8")
