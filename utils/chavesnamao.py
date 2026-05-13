import os
import re

from bs4 import BeautifulSoup
from urllib.parse import urljoin


MIN_LARGURA = 1200
MIN_ALTURA = 800


def extrair_imagens_chavesnamao(html: str, base_url: str) -> list[str]:
    def _normalizar_url(url_imagem: str) -> str:
        return urljoin(base_url, url_imagem.replace("\\/", "/"))

    def _chave_imagem(url_imagem: str) -> str:
        return os.path.basename(url_imagem.split("?", 1)[0])

    def _area_tamanho(url_imagem: str) -> int:
        match = re.search(r"/imn/(\d+)x(\d+)/", url_imagem)
        if not match:
            return 0

        return int(match.group(1)) * int(match.group(2))

    def _passa_filtro_qualidade(url_imagem: str) -> bool:
        match = re.search(r"/imn/(\d+)x(\d+)/", url_imagem)
        if not match:
            return False

        largura = int(match.group(1))
        altura = int(match.group(2))
        return largura >= MIN_LARGURA and altura >= MIN_ALTURA

    candidatos: dict[str, tuple[int, str]] = {}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("img"):
        valores = [
            tag.get("src"),
            tag.get("data-src"),
            tag.get("data-lazy-src"),
            tag.get("data-original"),
        ]

        srcset = tag.get("srcset")
        if srcset:
            for parte in srcset.split(","):
                url_parte = parte.strip().split(" ")[0]
                valores.append(url_parte)

        for valor in valores:
            if not valor or "/imn/" not in valor:
                continue

            url_imagem = _normalizar_url(valor)
            if not _passa_filtro_qualidade(url_imagem):
                continue

            chave = _chave_imagem(url_imagem)
            area = _area_tamanho(url_imagem)

            if chave not in candidatos or area > candidatos[chave][0]:
                candidatos[chave] = (area, url_imagem)

    if candidatos:
        return list(dict.fromkeys(url for _, url in candidatos.values()))

    padrao = r"https://www\.chavesnamao\.com\.br/imn/[^\"']+?\.(?:jpe?g|png|webp)"
    urls = [
        _normalizar_url(url_imagem)
        for url_imagem in re.findall(padrao, html, flags=re.IGNORECASE)
        if _passa_filtro_qualidade(_normalizar_url(url_imagem))
    ]

    return list(dict.fromkeys(urls))