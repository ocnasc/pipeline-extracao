# main.py

# PDF to Text & Image Analysis with OpenAI
# This script extracts text and images from PDF documents, sends them for AI analysis, and saves the results as JSON.

from pdf2image import convert_from_path
import base64
import fitz  # PyMuPDF (corrigido: "import pymupdf" pode dar erro)
from dotenv import load_dotenv
import concurrent.futures
import os
import io
from tqdm import tqdm
from openai import OpenAI
import json
from datetime import datetime
from prompts import *
import time
import tiktoken
import random
from openai import RateLimitError, APIError
from pathlib import Path

# -------------------------------------------------------------------
# Setup
# -------------------------------------------------------------------
load_dotenv()
now = datetime.now().strftime(r"%Y%m%dT%H%M%S")
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY não encontrada no arquivo .env")

client = OpenAI(api_key=api_key)

# Model configuration
ANALYSIS_MODEL = "gpt-4.1"
PPROC_MODEL = "gpt-5-mini"

# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
def count_tokens(model, text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


def estimate_total_tokens(model, texts, num_images):
    """Estima tokens considerando apenas 1 vez o prompt base e aplicando margem de segurança."""
    total = count_tokens(model, analysis_prompt)  # só uma vez
    for t in texts:
        total += count_tokens(model, t)           # texto da página
        total += 85                               # custo médio por imagem
    return int(total * 1.2)  # margem de 20%


def convert_doc_to_images(path):
    return convert_from_path(path)


def get_img_uri(img):
    png_buffer = io.BytesIO()
    img.save(png_buffer, format="PNG")
    png_buffer.seek(0)
    base64_png = base64.b64encode(png_buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{base64_png}"


def extract_text_by_page(path):
    with fitz.open(path) as doc:
        return [page.get_text("text") for page in doc]


def load_safe_json(raw_str):
    """Valida e corrige JSON malformatado retornado pela IA."""
    try:
        return json.loads(raw_str)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON inválido: {e}")
        cleaned = raw_str.strip().replace("```json", "").replace("```", "")
        try:
            return json.loads(cleaned)
        except Exception as e2:
            print(f"❌ Falhou ao corrigir JSON: {e2}")
            return {"error": "invalid_json", "raw": cleaned}


def split_list(lst, n):
    """Divide lista em blocos de tamanho n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# -------------------------------------------------------------------
# Processing functions
# -------------------------------------------------------------------
def safe_pproc(pproc_prompt, path, json_str, retries=3):
    backoff = 5
    for attempt in range(retries):
        try:
            return pproc(pproc_prompt, path, json_str)
        except (RateLimitError, APIError) as e:
            wait = backoff * (2 ** attempt) + random.uniform(0, 2)
            print(f"⚠️ Erro no pproc: {e}. Retentando em {wait:.1f}s...")
            time.sleep(wait)
    raise RuntimeError("❌ pproc falhou após várias tentativas")

def pproc(pproc_prompt, path, json_str):
    print(f"Processando arquivo {path}")

    file = client.files.create(
        file=open(path, "rb"),
        purpose="user_data"
    )

    json_sys_prompt = (
        f"{pproc_prompt}\n\n"
        f"Here is the extracted content so far. Do not summarize. "
        f"Expand and reorganize into the structured JSON format exactly as shown. "
        f"Preserve all details, conditions, and states: {json_str}"
    )

    response = client.responses.create(
        model=PPROC_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": file.id},
                    {"type": "input_text", "text": json_sys_prompt},
                ],
            }
        ],
    )
    if PPROC_MODEL == "gpt-5-mini":
        return response.output_text.replace("```json", "").replace("```", "")
    else:
        return str(response.output[0].content[0].text).replace("```json", "").replace("```", "")


def safe_silver_json(pdf, json, silver_json_prompt, retries=3):
    """Wrapper com retry logic e logging detalhado para silver_json."""
    backoff = 10

    for attempt in range(retries):
        try:
            print(f"\n{'='*60}")
            print(f"[SILVER_JSON] Tentativa {attempt + 1}/{retries}")
            print(f"{'='*60}")
            return silver_json(pdf, json, silver_json_prompt)

        except RateLimitError as e:
            wait = backoff * (2 ** attempt) + random.uniform(0, 3)
            print(f"\n⚠️ [SILVER_JSON] RateLimitError na tentativa {attempt + 1}/{retries}")
            print(f"   Detalhes: {e}")
            print(f"   Aguardando {wait:.1f}s antes de tentar novamente...")
            time.sleep(wait)

        except APIError as e:
            wait = backoff * (2 ** attempt) + random.uniform(0, 3)
            print(f"\n⚠️ [SILVER_JSON] APIError na tentativa {attempt + 1}/{retries}")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Código: {getattr(e, 'status_code', 'N/A')}")
            print(f"   Mensagem: {e}")
            print(f"   Aguardando {wait:.1f}s antes de tentar novamente...")
            time.sleep(wait)

        except Exception as e:
            print(f"\n❌ [SILVER_JSON] Erro inesperado na tentativa {attempt + 1}/{retries}")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensagem: {e}")
            print(f"   Detalhes completos:")
            import traceback
            traceback.print_exc()
            raise

    raise RuntimeError(f"❌ [SILVER_JSON] Falhou após {retries} tentativas")


def silver_json(pdf, json, silver_json_prompt):
    print(f"\n[SILVER_JSON] Iniciando processamento")
    print(f"[SILVER_JSON] PDF: {os.path.basename(pdf)}")
    print(f"[SILVER_JSON] JSON: {os.path.basename(json)}")

    try:
        # Lê o JSON como string
        print(f"[SILVER_JSON] Lendo arquivo JSON...")
        with open(json, "r", encoding="utf-8") as json_f:
            json_string = json_f.read()

        json_size_kb = len(json_string) / 1024
        print(f"[SILVER_JSON] Tamanho do JSON: {len(json_string)} caracteres ({json_size_kb:.2f} KB)")

        # Envia o PDF
        print(f"[SILVER_JSON] Enviando PDF para OpenAI...")
        pdf_size_mb = os.path.getsize(pdf) / (1024 * 1024)
        print(f"[SILVER_JSON] Tamanho do PDF: {pdf_size_mb:.2f} MB")

        with open(pdf, "rb") as pdf_f:
            pdf_file = client.files.create(file=pdf_f, purpose="user_data")

        print(f"[SILVER_JSON] PDF enviado com sucesso. File ID: {pdf_file.id}")

        # Cria a resposta
        print(f"[SILVER_JSON] Chamando API com modelo: {PPROC_MODEL}")
        print(f"[SILVER_JSON] Tamanho do prompt: {len(silver_json_prompt)} caracteres")

        response = client.responses.create(
            model=PPROC_MODEL,
            input=[
                {"role": "system", "content": silver_json_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": pdf_file.id},
                        {"type": "input_text", "text": json_string}
                    ],
                },
            ],
        )

        print(f"[SILVER_JSON] Resposta recebida com sucesso")

        # Renomeia o arquivo JSON para .tmp em vez de excluir
        print(f"[SILVER_JSON] Renomeando arquivo JSON para .tmp...")
        base, ext = os.path.splitext(json)
        novo_nome = base + ".tmp"
        os.rename(json, novo_nome)
        print(f"[SILVER_JSON] Arquivo renomeado: {os.path.basename(novo_nome)}")

        # Retorna o output do modelo
        output = response.output_text.replace("```json", "").replace("```", "")
        print(f"[SILVER_JSON] Tamanho da resposta: {len(output)} caracteres")
        print(f"[SILVER_JSON] Processamento concluído com sucesso\n")

        return output

    except Exception as e:
        print(f"\n❌ [SILVER_JSON] ERRO DURANTE EXECUÇÃO")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensagem: {e}")
        print(f"   Código de status: {getattr(e, 'status_code', 'N/A')}")
        raise




def analyze_doc_image(img, text, model=ANALYSIS_MODEL):
    img_uri = get_img_uri(img)
    return analyze_image(img_uri, text, model)


def analyze_image(data_uri, text, model=ANALYSIS_MODEL):
    """Analisa imagem + texto (sem retries automáticos)."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": analysis_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": text},
                ],
            },
        ],
        max_tokens=1000,
        temperature=0,
        top_p=0.1,
    )
    return response.choices[0].message.content


def contar_tags_imagem(caminho_arquivo):
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    def contar_recursivamente(obj):
        contador = 0
        if isinstance(obj, dict):
            for chave, valor in obj.items():
                if chave in ['image', 'images']:
                    contador += 1
                contador += contar_recursivamente(valor)
        elif isinstance(obj, list):
            for item in obj:
                contador += contar_recursivamente(item)
        return contador

    return contar_recursivamente(dados)


# -------------------------------------------------------------------
# Main pipeline
# -------------------------------------------------------------------
def pipeline(base_path, filename, general_information, selected_file=None, chunk_size=10):

    start_time = time.time()

    path_parcionados = Path(base_path) / "PDFs parcionados"

    raw_dir = Path(base_path) / "results" / "raw"
    silver_dir = Path(base_path) / "results" / "silver"

    if not os.path.isdir(path_parcionados):
        raise FileNotFoundError(f"Pasta não encontrada: {path_parcionados}")

    all_items = os.listdir(path_parcionados)
    files = [item for item in all_items if os.path.isfile(os.path.join(path_parcionados, item)) and item.lower().endswith(".pdf")]

    if selected_file:
        if selected_file not in files:
            raise FileNotFoundError(f"Arquivo selecionado '{selected_file}' não encontrado em {path_parcionados}")
        files = [selected_file]
    else:
        print("Nenhum arquivo selecionado — processando todos os PDFs da pasta.")

    now = datetime.now().strftime(r"%Y%m%dT%H%M%S")
    docs = []

    for f in files:
        pdf_path = os.path.join(path_parcionados, f)
        doc = {"filename": f}
        

        imgs = convert_doc_to_images(pdf_path)
        text = extract_text_by_page(pdf_path)
        pages_description = []

        print(f"Processando páginas do documento: {f}")

        for chunk in split_list(list(enumerate(imgs)), chunk_size):
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(analyze_doc_image, img, text[idx], ANALYSIS_MODEL) for idx, img in chunk]

                with tqdm(total=len(chunk)) as pbar:
                    for _ in concurrent.futures.as_completed(futures):
                        pbar.update(1)

                for future in futures:
                    pages_description.append(future.result())

        doc["pages_description"] = pages_description
        docs.append(doc)

        # Save raw results
        os.makedirs(raw_dir, exist_ok=True)
        raw_path = os.path.join(raw_dir, f"raw_{filename}.json")
        with open(raw_path, "w", encoding="utf-8") as file:
            json.dump(docs, file, ensure_ascii=False, indent=2)

        print(f"{os.path.basename(raw_path)} salvo com sucesso em {os.path.normpath(raw_path)}")

        with open(raw_path, "r", encoding="utf8") as file:
            json_parcial = file.read()

        pproc_json = load_safe_json(pproc(pproc_prompt, pdf_path, json_parcial))

        os.makedirs(silver_dir, exist_ok=True)
        stg_silver_path = os.path.join(silver_dir, f"tmp_silver_{filename}.json")
        with open(stg_silver_path, "w", encoding="utf8") as r:
            json.dump(pproc_json, r, ensure_ascii=False)

        final_prompt = silver_prompt(general_information)

        final_silver = load_safe_json(safe_silver_json(pdf_path, stg_silver_path, final_prompt))
        final_silver_path = os.path.join(silver_dir, f"silver_{filename}.json")

        with open(final_silver_path, "w", encoding="utf8") as r:
            json.dump(final_silver, r, ensure_ascii=False)

        total_images = contar_tags_imagem(final_silver_path)

        print(f"{os.path.basename(final_silver_path)} salvo com sucesso em {os.path.normpath(final_silver_path)}")
        print(f"Total de imagens encontradas: {total_images}")

        # Calcula o tempo total de execução
        end_time = time.time()
        elapsed_seconds = end_time - start_time
        print(f"Tempo total de execução da pipeline: {elapsed_seconds:.2f} segundos ({elapsed_seconds/60:.2f} minutos)")
