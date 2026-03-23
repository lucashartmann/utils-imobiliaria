import math
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import ollama


class Modelo:

    def __init__(self):
        self.modelo = ""
        self.embedding_model = "nomic-embed-text"
        self.ultima_metrica = {}
        self.ultimo_contexto_stats = {}

    def set_modelo(self, modelo):
        self.modelo = modelo

    def deletar(self, modelo):
        try:
            ollama.delete(modelo)
            return True
        except Exception as e:
            print(f"ERRO! Modelo.deletar {e}")
            return False

    def unload_model(self):
        try:
            ollama.generate(
                model=self.modelo,
                prompt="",
                keep_alive=0
            )
            return True
        except Exception as e:
            print(e)
            return False

    def pull(self, modelo):
        try:
            ollama.pull(modelo)
            return True
        except Exception as e:
            print(f"ERRO! Modelo.pull {e}")
            return False

    def listar_nome_modelos(self):
        lista = []
        try:
            response = ollama.list()
            for modelo in response.models:
                lista.append(modelo.model)
            return lista
        except Exception as e:
            print(f"ERRO! Modelo.listar_nome_modelos {e}")
            return []

    def obter_max_retry_sintaxe(self) -> int:
        nome = str(self.modelo or "").lower()
        match = re.search(r"(\d+(?:\.\d+)?)b", nome)
        if not match:
            return 1

        try:
            tamanho_b = float(match.group(1))
        except Exception:
            return 1

        return 2 if tamanho_b <= 3.0 else 1

    def _show_model_info(self):
        try:
            if not self.modelo:
                return {}
            info = ollama.show(self.modelo)
            return info if isinstance(info, dict) else {}
        except Exception as e:
            print(f"ERRO! Modelo._show_model_info {e}")
            return {}

    @staticmethod
    def estimar_tokens(texto: str) -> int:
        if not texto:
            return 0
        return max(1, int(len(texto) / 4))

    def obter_limite_contexto(self, padrao: int = 4096) -> int:
        info = self._show_model_info()

        candidatos = []

        model_info = info.get("model_info", {}) if isinstance(
            info, dict) else {}
        for key, value in model_info.items():
            key_lower = str(key).lower()
            if any(k in key_lower for k in ["context", "num_ctx", "max_position", "seq_length"]):
                try:
                    candidatos.append(int(value))
                except Exception:
                    pass

        parameters = info.get("parameters", "")
        if isinstance(parameters, str):
            for match in re.findall(r"(?:num_ctx|context_length|max_context)\s+(\d+)", parameters, flags=re.IGNORECASE):
                try:
                    candidatos.append(int(match))
                except Exception:
                    pass

        options = info.get("options", {}) if isinstance(info, dict) else {}
        if isinstance(options, dict):
            for key in ["num_ctx", "context_length", "max_context"]:
                if key in options:
                    try:
                        candidatos.append(int(options[key]))
                    except Exception:
                        pass

        validos = [c for c in candidatos if c > 256]
        if validos:
            return max(validos)
        return padrao

    def suporta_imagem(self) -> bool:
        info = self._show_model_info()

        capacidades = info.get(
            "capabilities", []) if isinstance(info, dict) else []
        if isinstance(capacidades, list):
            caps = {str(c).lower() for c in capacidades}
            if "vision" in caps or "image" in caps or "multimodal" in caps:
                return True

        details = info.get("details", {}) if isinstance(info, dict) else {}
        family = str(details.get("family", "")).lower()
        families = [str(f).lower() for f in details.get("families", [])] if isinstance(
            details.get("families", []), list) else []
        if any("clip" in f or "vision" in f for f in [family] + families):
            return True

        nome = str(self.modelo).lower()
        return any(v in nome for v in ["llava", "bakllava", "moondream", "vision"])

    @staticmethod
    def _dividir_em_chunks_tokens(texto: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
        palavras = texto.split()
        if not palavras:
            return []

        if len(palavras) <= chunk_size:
            return [" ".join(palavras)]

        chunks = []
        inicio = 0
        passo = max(1, chunk_size - overlap)

        while inicio < len(palavras):
            fim = min(inicio + chunk_size, len(palavras))
            chunks.append(" ".join(palavras[inicio:fim]))
            if fim >= len(palavras):
                break
            inicio += passo

        return chunks

    def gerar_embedding(self, texto: str, embedding_model: Optional[str] = None) -> Optional[List[float]]:
        model_name = embedding_model or self.embedding_model
        candidatos = [model_name]
        if model_name != self.embedding_model:
            candidatos.append(self.embedding_model)

        for nome_modelo in candidatos:
            try:
                resposta = ollama.embed(model=nome_modelo, input=texto)
                embeddings = resposta.get("embeddings", []) if isinstance(
                    resposta, dict) else []
                if embeddings and isinstance(embeddings[0], list):
                    return embeddings[0]
            except Exception:
                pass

            try:
                resposta = ollama.embeddings(model=nome_modelo, prompt=texto)
                if isinstance(resposta, dict) and isinstance(resposta.get("embedding"), list):
                    return resposta["embedding"]
            except Exception:
                pass

        return None

    @staticmethod
    def _similaridade_cosseno(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return -1.0

        produto = sum(a * b for a, b in zip(v1, v2))
        norma_1 = math.sqrt(sum(a * a for a in v1))
        norma_2 = math.sqrt(sum(b * b for b in v2))
        if norma_1 == 0 or norma_2 == 0:
            return -1.0
        return produto / (norma_1 * norma_2)

    def _ler_arquivo_texto(self, caminho: str) -> Optional[str]:
        try:
            return Path(caminho).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return Path(caminho).read_text(encoding="latin-1")
            except Exception as e:
                print(f"ERRO! Modelo._ler_arquivo_texto {e}")
                return None
        except Exception as e:
            print(f"ERRO! Modelo._ler_arquivo_texto {e}")
            return None

    def montar_contexto_arquivos(
        self,
        caminhos: List[str],
        pergunta: str,
        margem_resposta_tokens: int = 1200,
        chunk_size: int = 800,
        overlap: int = 120,
        top_k: int = 6,
    ) -> Tuple[str, str, int, int]:
        limite_modelo = self.obter_limite_contexto()
        orcamento_prompt = max(512, limite_modelo - margem_resposta_tokens)

        blocos = []
        for caminho in caminhos:
            conteudo = self._ler_arquivo_texto(caminho)
            if not conteudo:
                continue
            blocos.append(f"Arquivo: {caminho}\n```\n{conteudo}\n```")

        if not blocos:
            self.ultimo_contexto_stats = {
                "chunks_total": 0,
                "chunks_selecionados": 0,
                "tokens_contexto": 0,
            }
            return "", "sem_arquivos", 0, limite_modelo

        contexto_completo = "\n\n".join(blocos)
        prompt_completo = f"{pergunta}\n\n{contexto_completo}"
        tokens_prompt = self.estimar_tokens(prompt_completo)

        if tokens_prompt <= orcamento_prompt:
            self.ultimo_contexto_stats = {
                "chunks_total": 0,
                "chunks_selecionados": 0,
                "tokens_contexto": tokens_prompt,
            }
            return contexto_completo, "arquivo_inteiro", tokens_prompt, limite_modelo

        chunks_metadados = []
        for caminho in caminhos:
            conteudo = self._ler_arquivo_texto(caminho)
            if not conteudo:
                continue
            chunks = self._dividir_em_chunks_tokens(
                conteudo, chunk_size=chunk_size, overlap=overlap)
            for idx, chunk in enumerate(chunks, 1):
                chunks_metadados.append({
                    "arquivo": caminho,
                    "idx": idx,
                    "texto": chunk,
                })

        if not chunks_metadados:
            self.ultimo_contexto_stats = {
                "chunks_total": 0,
                "chunks_selecionados": 0,
                "tokens_contexto": tokens_prompt,
            }
            return contexto_completo, "fallback_completo", tokens_prompt, limite_modelo

        emb_pergunta = self.gerar_embedding(pergunta)
        if not emb_pergunta:
            selecionados = chunks_metadados[:top_k]
        else:
            pontuados = []
            for item in chunks_metadados:
                emb_chunk = self.gerar_embedding(item["texto"])
                if emb_chunk:
                    score = self._similaridade_cosseno(emb_pergunta, emb_chunk)
                else:
                    score = -1.0
                pontuados.append((score, item))

            pontuados.sort(key=lambda x: x[0], reverse=True)
            selecionados = [item for _, item in pontuados[:top_k]]

        contexto_chunks = []
        acumulado_tokens = self.estimar_tokens(pergunta)
        for item in selecionados:
            bloco = (
                f"Arquivo: {item['arquivo']}\n"
                f"Chunk: {item['idx']}\n"
                f"```\n{item['texto']}\n```"
            )
            custo = self.estimar_tokens(bloco)
            if acumulado_tokens + custo > orcamento_prompt and contexto_chunks:
                break
            contexto_chunks.append(bloco)
            acumulado_tokens += custo

        if not contexto_chunks:
            contexto_chunks.append(
                f"Arquivo: {selecionados[0]['arquivo']}\nChunk: {selecionados[0]['idx']}\n```\n{selecionados[0]['texto']}\n```"
            )

        self.ultimo_contexto_stats = {
            "chunks_total": len(chunks_metadados),
            "chunks_selecionados": len(contexto_chunks),
            "tokens_contexto": acumulado_tokens,
        }

        return "\n\n".join(contexto_chunks), "rag_chunks", acumulado_tokens, limite_modelo

    def enviar_mensagem(self, mensagem, imagens=None):
        try:
            acumulado = ""
            ultima_parte = None
            if not imagens:
                resposta = ollama.chat(
                    model=self.modelo,
                    messages=[{'role': 'user', 'content': f'{mensagem}'}],
                    stream=True,
                )
            else:
                imagens = imagens if isinstance(
                    imagens, list) else [imagens]
                
                print(f"Enviando mensagem com {len(imagens)} imagens para o modelo {self.modelo}...")
                print(imagens)
                resposta = ollama.chat(
                    model=self.modelo,
                    messages=[
                        {'role': 'user', 'content': f'{mensagem}', 'images': imagens}],
                    stream=True,
                )

            for parte in resposta:
                ultima_parte = parte
                conteudo = ""

                if isinstance(parte, dict):
                    message = parte.get("message", {})
                    if isinstance(message, dict):
                        conteudo = message.get("content", "") or ""
                else:
                    message_obj = getattr(parte, "message", None)
                    if message_obj is not None:
                        conteudo = getattr(message_obj, "content", "") or ""

                if conteudo:
                    acumulado += conteudo

            self.ultima_metrica = self._extrair_metricas_ollama(ultima_parte)

            return acumulado
        except Exception as e:
            print(f"ERRO! Modelo.enviar_mensagem {e}")
            self.ultima_metrica = {}
            return None

    @staticmethod
    def _extrair_metricas_ollama(parte) -> dict:
        if not parte:
            return {}

        campos = [
            "prompt_eval_count",
            "eval_count",
            "prompt_eval_duration",
            "eval_duration",
            "total_duration",
        ]

        metricas = {}
        if isinstance(parte, dict):
            for campo in campos:
                valor = parte.get(campo)
                if valor is not None:
                    metricas[campo] = valor
            return metricas

        for campo in campos:
            valor = getattr(parte, campo, None)
            if valor is not None:
                metricas[campo] = valor
        return metricas

    def enviar_mensagem_sync(self, mensagem, caminho_image=None):
        return self.enviar_mensagem(mensagem, caminho_image)
