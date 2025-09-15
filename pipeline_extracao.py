# main.py

# PDF to Text & Image Analysis with OpenAI
# This script extracts text and images from PDF documents, sends them for AI analysis, and saves the results as JSON.

from pdf2image import convert_from_path
import base64
import pymupdf
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

# -------------------------------------------------------------------
# Setup
# -------------------------------------------------------------------
load_dotenv()
now = datetime.now().strftime(r"%Y%m%dT%H%M%S")
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


# -------------------------------------------------------------------
# Functions: PDF to images & text
# -------------------------------------------------------------------
def convert_doc_to_images(path):
    images = convert_from_path(path)
    return images


def get_img_uri(img):
    png_buffer = io.BytesIO()
    img.save(png_buffer, format="PNG")
    png_buffer.seek(0)
    base64_png = base64.b64encode(png_buffer.read()).decode("utf-8")
    data_uri = f"data:image/png;base64,{base64_png}"
    return data_uri


def extract_text_by_page(path):
    with pymupdf.open(path) as doc:
        texts = [page.get_text("text") for page in doc]
    return texts


# -------------------------------------------------------------------
# Processing functions
# -------------------------------------------------------------------
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
        model="gpt-4o",
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
    data = (
        str(response.output[0].content[0].text)
        .replace("```json", "")
        .replace("```", "")
    )
    return data


def analyze_image(data_uri, text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": analysis_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"{data_uri}"}},
                    {"type": "text", "text": text},
                ],
            },
        ],
        max_tokens=1000,
        temperature=0,
        top_p=0.1,
    )
    return response.choices[0].message.content


def analyze_doc_image(img, text):
    img_uri = get_img_uri(img)
    data = analyze_image(img_uri, text)
    return data


# -------------------------------------------------------------------
# Main pipeline
# -------------------------------------------------------------------
def pipeline(path_parcionados):
    files_path = path_parcionados

    all_items = os.listdir(files_path)
    files = [item for item in all_items if os.path.isfile(os.path.join(files_path, item))]

    for idx, f in enumerate(files):
        print(f"{idx}. {f}")

    try:
        answer = int(input("Digite o número do documento que você quer processar:\n"))
        files = [files[answer]]
    except Exception as e:
        print(f"ERROR ::: {e}")

    docs = []

    for f in files:
        path = f"{files_path}/{f}"
        doc = {"filename": f}
        filename = f.split(".")[0]

        # Convert PDF
        imgs = convert_doc_to_images(path)
        text = extract_text_by_page(path)
        pages_description = []

        print(f"Processando páginas do documento: {f}")

        # Concurrent execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(analyze_doc_image, img, text[idx]) for idx, img in enumerate(imgs)]

            with tqdm(total=len(imgs)) as pbar:
                for _ in concurrent.futures.as_completed(futures):
                    pbar.update(1)

            for future in futures:
                res = future.result()
                pages_description.append(res)

        doc["pages_description"] = pages_description
        docs.append(doc)

        # Save raw results
        raw_path = f'./json_results/raw/raw_{filename}_{now}.json'
        with open(raw_path, "w", encoding="utf-8") as file:
            json.dump(docs, file, ensure_ascii=False, indent=2)

        print(f"raw_{filename}_{now}.json salvo com sucesso em {raw_path}")

        time.sleep(10)

        with open(raw_path, "r", encoding="utf8") as file:
            json_parcial = file.read()

        stg_json = pproc(pproc_prompt, path, json_parcial)

        final_json = json.loads(stg_json)

        bronze_path = f"./json_results/bronze/bronze_{filename}_{now}.json"
        with open(bronze_path, "w", encoding="utf8") as r:
            json.dump(final_json, r, ensure_ascii=False)

        print(f"bronze_{filename}_{now}.json salvo com sucesso em {bronze_path}")
