import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import subprocess
import hashlib
from PIL import Image, ImageOps
import cv2

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")
MEDIA_THUMB_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".avif",
        ".bmp",
        ".gif",
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
    }
)
FFPROBE_TIMEOUT = 10
FFMPEG_TIMEOUT = 1800
DISCARD_EXTENSIONS = (".txt", ".url", ".ini", ".db", ".json", ".xml", ".html", ".md", ".bat", ".exe", ".lnk", ".pdf", ".docx", ".xlsx")


def _normalizar_thumb(imagem: Image.Image) -> bytes:
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGBA")
    imagem = ImageOps.contain(imagem, (256, 256))
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    pos_x = (256 - imagem.width) // 2
    pos_y = (256 - imagem.height) // 2
    canvas.paste(imagem, (pos_x, pos_y), imagem)
    return canvas.tobytes()


def apagar_duplicados_por_thumb(pasta: str, max_workers: int | None = None):
    with os.scandir(pasta) as it:
        arquivos = [
            e
            for e in it
            if e.is_file()
            and os.path.splitext(e.name)[1].lower() in MEDIA_THUMB_EXTENSIONS
        ]

    def _processar(entry):
        return entry.name, entry.stat().st_size, obter_assinatura_thumb(entry.path)

    grupos = {}
    erros = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = [executor.submit(_processar, e) for e in arquivos]
        for futuro in as_completed(futuros):
            nome, tamanho, assinatura = futuro.result()
            if not assinatura:
                erros += 1
                continue
            grupos.setdefault(assinatura, []).append((nome, tamanho))

    removidos = 0
    unicos = 0

    for assinatura, lista in grupos.items():
        if len(lista) <= 1:
            unicos += 1
            continue

        manter = escolher_arquivo_para_manter(pasta, lista)

        for arquivo, _ in lista:
            if arquivo != manter[0] and ".part" not in arquivo:
                try:
                    os.remove(os.path.join(pasta, arquivo))
                    removidos += 1
                    print(f"🗑️ Thumb duplicada removida: {pasta}: {arquivo}")
                except Exception as e:
                    print(f"❌ Erro ao remover thumb duplicada {pasta}: {arquivo}: {e}")


def converter_midias(pasta: str):
    with os.scandir(pasta) as it:
        entradas = [e for e in it if e.is_file()]

    for entry in entradas:
        arquivo = entry.name
        caminho = entry.path
        nome, ext = os.path.splitext(arquivo)
        ext = ext.lower()

        if ext in ('.webp', '.avif'):
            print(f'🖼️ Encontrado: {pasta}: {arquivo}')
            try:
                with Image.open(caminho) as img:

                    if getattr(img, "is_animated", False):
                        gif_path = os.path.join(pasta, nome + '.gif')
                        frames = []

                        for frame in range(img.n_frames):
                            img.seek(frame)
                            frames.append(img.copy())

                        frames[0].save(
                            gif_path,
                            save_all=True,
                            append_images=frames[1:],
                            loop=0,
                            duration=img.info.get("duration", 100)
                        )

                        os.remove(caminho)
                        print(
                            f'🖼️ Convertido: {pasta}: {arquivo} -> {os.path.basename(gif_path)}')
                        continue

                    if img.mode == "RGBA":
                        novo = os.path.join(pasta, nome + '.png')
                        img.save(novo, 'PNG')
                    else:
                        img = img.convert("RGB")
                        novo = os.path.join(pasta, nome + '.jpg')
                        img.save(novo, 'JPEG', quality=95)

                os.remove(caminho)
                print(
                    f'🖼️ Convertido: {pasta}: {arquivo} -> {os.path.basename(novo)}')

            except Exception as e:
                continue

        elif ext == '.webm':
            tamanho = entry.stat().st_size
            if tamanho > 200 * 1024 * 1024:  
                continue
            print(f'🎬 Convertendo vídeo: {pasta}: {arquivo}')
            mp4_path = os.path.join(pasta, nome + '.mp4')

            comando = [
                'ffmpeg', '-y', '-i', caminho,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict', 'experimental',
                mp4_path
            ]

            try:
                subprocess.run(
                    comando,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=FFMPEG_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                continue

            if os.path.exists(mp4_path):
                os.remove(caminho)
                print(
                    f'🎬 Convertido: {pasta}: {arquivo} -> {os.path.basename(mp4_path)}')

        elif ext in DISCARD_EXTENSIONS:
            print(f'🗑️ Removendo: {pasta}: {arquivo}')
            os.remove(caminho)

        elif ext == "":
            print(f'🗑️ Removendo sem extensão: {pasta}: {arquivo}')
            os.remove(caminho)


def escolher_arquivo_para_manter(pasta: str, lista: list) -> tuple:
    manter = max(lista, key=lambda x: x[1])
    maiores = [item for item in lista if item[1] == manter[1]]

    if len(maiores) == 1:
        return manter

    candidatos = []
    for arquivo, tamanho in maiores:
        caminho = os.path.join(pasta, arquivo)
        metricas_midia = obter_metricas_midia(caminho)
        try:
            mtime = os.path.getmtime(caminho)
        except Exception:
            mtime = 0.0
        score = (tamanho, *metricas_midia, mtime, arquivo)
        candidatos.append((score, arquivo, tamanho))

    _, arquivo_escolhido, tamanho_escolhido = max(candidatos, key=lambda x: x[0])
    return (arquivo_escolhido, tamanho_escolhido)


def obter_metricas_midia(caminho: str) -> tuple:
    # Tupla ordenada por prioridade para desempate entre arquivos de mesmo tamanho.
    fallback = (0.0, 0.0, 0, 0.0, 0.0)
    comando = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        caminho,
    ]

    try:
        proc = subprocess.run(
            comando, capture_output=True, text=True, timeout=FFPROBE_TIMEOUT
        )
        if proc.returncode != 0 or not proc.stdout:
            return fallback

        info = json.loads(proc.stdout)
        formato = info.get("format", {})
        streams = info.get("streams", [])

        bitrate_total = float(formato.get("bit_rate") or 0)
        duracao = float(formato.get("duration") or 0)

        bitrate_video = 0.0
        bitrate_audio = 0.0
        pixels = 0
        fps = 0.0

        for stream in streams:
            tipo = stream.get("codec_type")
            bitrate_stream = float(stream.get("bit_rate") or 0)

            if tipo == "video":
                bitrate_video = max(bitrate_video, bitrate_stream)
                largura = int(stream.get("width") or 0)
                altura = int(stream.get("height") or 0)
                pixels = max(pixels, largura * altura)
                fps = max(fps, _parse_ffprobe_rate(stream.get("avg_frame_rate", "0/1")))
            elif tipo == "audio":
                bitrate_audio = max(bitrate_audio, bitrate_stream)

        return (bitrate_total, bitrate_video, pixels, duracao, fps + bitrate_audio)
    except Exception:
        return fallback


def _parse_ffprobe_rate(rate_value: str) -> float:
    if not rate_value or rate_value == "N/A":
        return 0.0

    if "/" in rate_value:
        try:
            num, den = rate_value.split("/", 1)
            den_f = float(den)
            if den_f == 0:
                return 0.0
            return float(num) / den_f
        except Exception:
            return 0.0

    try:
        return float(rate_value)
    except Exception:
        return 0.0


def obter_assinatura_thumb(caminho: str):
    ext = os.path.splitext(caminho)[1].lower()

    try:
        if ext in VIDEO_EXTENSIONS:
            captura = cv2.VideoCapture(caminho)
            try:
                ok, frame = captura.read()
            finally:
                captura.release()

            if not ok or frame is None:
                return None

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            imagem = Image.fromarray(frame_rgb)
        else:
            with Image.open(caminho) as imagem_aberta:
                imagem = imagem_aberta.copy()

        dados = _normalizar_thumb(imagem)
        return hashlib.sha256(dados).hexdigest()
    except Exception:
        return None


if __name__ == "__main__":

    BASE_DIRS = [
        r"A:\Projetos\utils-imobiliaria\Destino",
        r"A:\Projetos\utils-imobiliaria\Imagens",
    ]

    for base_dir in BASE_DIRS:
        for pasta in sorted(
            [
                nome
                for nome in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, nome))
            ],
            key=lambda x: os.path.getmtime(os.path.join(base_dir, x)),
            reverse=True,
        ):
            caminho = os.path.join(base_dir, pasta)
            print(f"📂 Processando pasta: {pasta}")
            apagar_duplicados_por_thumb(caminho)
            converter_midias(caminho)
