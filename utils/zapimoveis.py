import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse



_RE_CDN_ZAP = re.compile(
    r"resizedimgs\.zapimoveis\.com\.br"
    r"/(?:fit-in|crop)"
    r"/\d+x\d+"
    r"(?:/filters:[^/]*)?"
    r"/(.+)",
    re.IGNORECASE,
)


def _url_original(url: str) -> str:
    m = _RE_CDN_ZAP.search(url)
    if m:
        return "https://" + m.group(1)
    return url


def _eh_imagem(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".avif"))



def obter_html_renderizado_zapimoveis(url: str) -> str | None:
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
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
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



def extrair_imagens_zapimoveis(html: str, base_url: str) -> list[str]:
    vistos: set[str] = set()
    urls_originais: list[str] = []

    def _adicionar(url_thumb: str) -> None:
        orig = _url_original(url_thumb.replace("\\/", "/"))
        if orig not in vistos and _eh_imagem(orig):
            vistos.add(orig)
            urls_originais.append(orig)

    soup = BeautifulSoup(html, "html.parser")
    tag_next = soup.find("script", id="__NEXT_DATA__")
    if tag_next and tag_next.string:
        try:
            dados = json.loads(tag_next.string)
            page_props = dados.get("props", {}).get("pageProps", {})
            _coletar_imagens_json(page_props, _adicionar)
        except Exception:
            pass

    if urls_originais:
        return urls_originais

    _RE_CDN_BRUTA = re.compile(
        r"https?://resizedimgs\.zapimoveis\.com\.br"
        r"/(?:fit-in|crop)/\d+x\d+"
        r"(?:/filters:[^\s>]*)?"
        r"/[^\s\"'>]+?\.(?:jpe?g|png|webp)",
        re.IGNORECASE,
    )
    for m in _RE_CDN_BRUTA.finditer(html):
        _adicionar(m.group(0))

    _RE_ORIG_BRUTA = re.compile(
        r"https?://vr\.ob\.(?:prod\.)?zapimoveis\.com\.br"
        r"/[^\s\"'>]+?\.(?:jpe?g|png|webp)",
        re.IGNORECASE,
    )
    for m in _RE_ORIG_BRUTA.finditer(html):
        url_limpa = m.group(0).replace("\\/", "/")
        if url_limpa not in vistos and _eh_imagem(url_limpa):
            vistos.add(url_limpa)
            urls_originais.append(url_limpa)

    if urls_originais:
        return urls_originais

    for tag in soup.find_all(["img", "source"]):
        for atributo in ["srcset", "data-srcset"]:
            srcset = tag.get(atributo)
            if srcset:
                melhor = _melhor_srcset(srcset)
                if melhor:
                    _adicionar(urljoin(base_url, melhor.replace("\\/", "/")))
                break
        else:
            for atributo in ["src", "data-src", "data-lazy", "data-original"]:
                valor = tag.get(atributo)
                if valor:
                    _adicionar(urljoin(base_url, valor.replace("\\/", "/")))
                    break

    return urls_originais


def _coletar_imagens_json(obj: object, adicionar, depth: int = 0) -> None:
    if depth > 12:
        return

    if isinstance(obj, str):
        if re.search(r"\.(?:jpe?g|png|webp)", obj, re.I) and obj.startswith("http"):
            adicionar(obj)
        return

    if isinstance(obj, list):
        for item in obj:
            _coletar_imagens_json(item, adicionar, depth + 1)
        return

    if isinstance(obj, dict):
        CHAVES_IMAGEM = {"images", "fotos", "photos", "medias", "gallery", "galeria", "imgs"}
        for chave, val in obj.items():
            if chave.lower() in CHAVES_IMAGEM:
                _coletar_imagens_json(val, adicionar, depth + 1)

        for chave, val in obj.items():
            if chave.lower() not in CHAVES_IMAGEM:
                _coletar_imagens_json(val, adicionar, depth + 1)


def _pontuar_descritor(descritor: str) -> float:
    m = re.match(r"^(\d+(?:\.\d+)?)([wx])$", descritor.strip(), re.IGNORECASE)
    if not m:
        return 0.0
    valor = float(m.group(1))
    return valor * 10000.0 if m.group(2).lower() == "x" else valor


def _melhor_srcset(srcset: str) -> str | None:
    melhor_url, melhor_score = None, -1.0
    for parte in srcset.split(","):
        pedacos = parte.strip().split()
        if not pedacos:
            continue
        score = _pontuar_descritor(pedacos[1]) if len(pedacos) > 1 else 0.0
        if score >= melhor_score:
            melhor_score = score
            melhor_url = pedacos[0]
    return melhor_url