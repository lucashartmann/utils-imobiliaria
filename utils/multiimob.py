import re
from urllib.parse import urljoin


PADRAO_URL_IMAGEM = re.compile(
    r"https?://cdn\.vistahost\.com\.br/multiimo/vista\.imobi/fotos/\d+/[^\"'\s>]+?\.(?:jpe?g|png|webp)",
    flags=re.IGNORECASE,
)


def extrair_imagens_multiimob(html: str, base_url: str) -> list[str]:
    def _normalizar_url(url_imagem: str) -> str:
        return urljoin(base_url, url_imagem.replace("\\/", "/"))

    def _eh_preview(url_imagem: str) -> bool:
        return bool(re.search(r"_p\.(?:jpe?g|png|webp)(?:$|\?)", url_imagem, flags=re.IGNORECASE))

    urls: list[str] = []
    vistos: set[str] = set()

    for url_imagem in PADRAO_URL_IMAGEM.findall(html):
        url_normalizada = _normalizar_url(url_imagem)

        if _eh_preview(url_normalizada):
            continue

        if url_normalizada not in vistos:
            vistos.add(url_normalizada)
            urls.append(url_normalizada)

    return urls