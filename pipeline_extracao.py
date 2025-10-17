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
client = OpenAI(api_key=api_key)


ANALYSIS_MODEL_DEFAULT = "gpt-4.1"#"gpt-4o-mini"
ANALYSIS_MODEL_LARGE = "gpt-4.1"
PPROC_MODEL = "gpt-5-mini"

# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
# def create_directories(base_path):
#     """
#     Cria a estrutura de pastas a partir de base_path fornecido pelo usuário.
#     Não cria a pasta pai fixa, apenas subpastas.
#     """
#     diretorios = [
#         Path(base_path) / "pdfs" / "brutos",
#         Path(base_path) / "pdfs" / "parcionados",
#         Path(base_path) / "json_results" / "raw",
#         Path(base_path) / "json_results" / "bronze",
#         Path(base_path) / "json_results" / "silver",
#         Path(base_path) / "json_results" / "gold",
#     ]

#     for d in diretorios:
#         d.mkdir(parents=True, exist_ok=True)
#         print(f"Diretório verificado/criado: {d}")

#     return diretorios  # útil para saber onde colocar os arquivos


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


import os

def silver_json(pdf, json, silver_json_prompt):
    print(f"Comparando arquivos e gerando SILVER:\n###> {os.path.basename(pdf)} e {os.path.basename(json)} <###")

    # Envia o PDF
    with open(pdf, "rb") as pdf_f:
        pdf_file = client.files.create(file=pdf_f, purpose="user_data")
    
    # Lê o JSON como string
    with open(json, "r", encoding="utf-8") as json_f:
        json_string = json_f.read()

    # Cria a resposta
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

    # Renomeia o arquivo JSON para .tmp em vez de excluir
    base, ext = os.path.splitext(json)
    novo_nome = base + ".tmp"
    os.rename(json, novo_nome)

    # Retorna o output do modelo
    return response.output_text.replace("```json", "").replace("```", "")




def analyze_doc_image(img, text, model=ANALYSIS_MODEL_DEFAULT):
    img_uri = get_img_uri(img)
    return analyze_image(img_uri, text, model)


def analyze_image(data_uri, text, model=ANALYSIS_MODEL_DEFAULT):
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

        # estimated_tokens = estimate_total_tokens(ANALYSIS_MODEL_DEFAULT, text, len(imgs))

        # if estimated_tokens > 200_000:
        #     chosen_model = ANALYSIS_MODEL_LARGE
        #     print(f"⚠️ Estimado {estimated_tokens} tokens, trocando para {chosen_model}")
        # else:
        #     chosen_model = ANALYSIS_MODEL_DEFAULT
        #     print(f"✅ Estimado {estimated_tokens} tokens, mantendo {chosen_model}")

        # Processamento em blocos (chunk_size páginas de cada vez)

        print(f"Processando páginas do documento: {f}")
        chosen_model = ANALYSIS_MODEL_LARGE


        for chunk in split_list(list(enumerate(imgs)), chunk_size):
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(analyze_doc_image, img, text[idx], chosen_model) for idx, img in chunk]

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

        final_silver = load_safe_json(silver_json(pdf_path, stg_silver_path, final_prompt))
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
