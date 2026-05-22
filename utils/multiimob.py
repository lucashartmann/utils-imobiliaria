import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


PADRAO_URL_IMAGEM = re.compile(
    r"https?://cdn\.vistahost\.com\.br/multiimo/vista\.imobi/fotos/\d+/[^\"'\s>]+?\.(?:jpe?g|png|webp)",
    flags=re.IGNORECASE,
)

PADRAO_URL_IMAGEM_URBAN = re.compile(
    r"https?://www\.urban\.imb\.br/media/imoveis/\d+/[^\"'\s>]+?\.(?:jpe?g|png|webp)",
    flags=re.IGNORECASE,
)


def _obter_id_imovel(base_url: str) -> str | None:
    match = re.search(r"/imovel/(\d+)/", base_url)
    if not match:
        return None

    return match.group(1)


def obter_html_renderizado_urban(url: str) -> str | None:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception:
        return None

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-BR")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        driver.get(url)
        return driver.page_source
    except Exception:
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def extrair_imagens_multiimob(html: str, base_url: str) -> list[str]:
    def _normalizar_url(url_imagem: str) -> str:
        return urljoin(base_url, url_imagem.replace("\\/", "/"))

    def _eh_preview(url_imagem: str) -> bool:
        return bool(re.search(r"_p\.(?:jpe?g|png|webp)(?:$|\?)", url_imagem, flags=re.IGNORECASE))

    urls: list[str] = []
    vistos: set[str] = set()

    if "urban.imb.br" in base_url:
        imovel_id = _obter_id_imovel(base_url)
        soup = BeautifulSoup(html, "html.parser")

        def _adicionar_url(url_imagem: str | None):
            if not url_imagem:
                return

            url_normalizada = _normalizar_url(url_imagem)

            if imovel_id and f"/media/imoveis/{imovel_id}/" not in url_normalizada:
                return

            if "/media/imoveis/" not in url_normalizada:
                return

            if url_normalizada in vistos:
                return

            vistos.add(url_normalizada)
            urls.append(url_normalizada)

        for img in soup.find_all("img"):
            for atributo in ["src", "data-src", "data-lazy", "data-original"]:
                _adicionar_url(img.get(atributo))

            srcset = img.get("srcset")
            if srcset:
                melhor_url = None
                melhor_largura = -1

                for parte in srcset.split(","):
                    pedacos = parte.strip().split()
                    if not pedacos:
                        continue

                    url_parte = pedacos[0]
                    largura = 0

                    if len(pedacos) > 1:
                        match_largura = re.search(r"(\d+)w$", pedacos[1])
                        if match_largura:
                            largura = int(match_largura.group(1))

                    if largura >= melhor_largura:
                        melhor_largura = largura
                        melhor_url = url_parte

                _adicionar_url(melhor_url)

        if urls:
            return urls

    for url_imagem in PADRAO_URL_IMAGEM.findall(html):
        url_normalizada = _normalizar_url(url_imagem)

        if _eh_preview(url_normalizada):
            continue

        if url_normalizada not in vistos:
            vistos.add(url_normalizada)
            urls.append(url_normalizada)

    imovel_id = _obter_id_imovel(base_url)

    for url_imagem in PADRAO_URL_IMAGEM_URBAN.findall(html):
        url_normalizada = _normalizar_url(url_imagem)

        if imovel_id and f"/media/imoveis/{imovel_id}/" not in url_normalizada:
            continue

        if url_normalizada not in vistos:
            vistos.add(url_normalizada)
            urls.append(url_normalizada)

    return urls