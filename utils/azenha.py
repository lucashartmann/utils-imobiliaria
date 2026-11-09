import re
from html import unescape

from bs4 import BeautifulSoup


_RE_GOOGLE_IMG = re.compile(
    r"https?://lh\d\.googleusercontent\.com/[A-Za-z0-9_-]+",
    flags=re.IGNORECASE,
)


def _url_original(url_imagem: str) -> str | None:
    match = _RE_GOOGLE_IMG.match(unescape(url_imagem).replace("\\/", "/").strip())
    if not match:
        return None

    # "=s0" pede a imagem no tamanho original ao CDN do Google
    return f"{match.group(0)}=s0"


def extrair_imagens_azenha(html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    def _adicionar(url_imagem: str | None) -> None:
        if not url_imagem:
            return

        url_original = _url_original(url_imagem)
        if url_original and url_original not in vistos:
            vistos.add(url_original)
            urls.append(url_original)

    soup = BeautifulSoup(html, "html.parser")

    # Galeria principal do imóvel (evita fotos de imóveis relacionados)
    galeria = soup.select_one(".lh-photos")
    if galeria:
        for img in galeria.find_all("img"):
            for atributo in ["src", "data-src", "data-lazy-src", "data-original"]:
                _adicionar(img.get(atributo))

    if urls:
        return urls

    for url_imagem in _RE_GOOGLE_IMG.findall(html):
        _adicionar(url_imagem)

    return urls
