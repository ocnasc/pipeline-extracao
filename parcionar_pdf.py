# parcionar_pdf.py
import fitz  # PyMuPDF
from pathlib import Path

def parcionar(pages, section_name, pdf_path, output_dir):
    """
    Particiona um PDF em uma seção específica usando PyMuPDF.

    :param pages: lista [primeira_pagina, ultima_pagina] (base 1)
    :param section_name: nome da seção
    :param pdf_path: caminho completo para o PDF bruto
    :param output_dir: pasta onde o PDF particionado será salvo
    """
    first_page, last_page = pages

    if first_page < 1 or last_page < first_page:
        raise ValueError("Páginas inválidas para particionar.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)  # abre o PDF
    total_pages = doc.page_count

    if last_page > total_pages:
        last_page = total_pages  # não extrapolar

    # cria novo PDF
    new_doc = fitz.open()

    # fitz indexa páginas a partir de 0
    for i in range(first_page - 1, last_page):
        new_doc.insert_pdf(doc, from_page=i, to_page=i)

    output_file = output_dir / f"{section_name}.pdf"
    new_doc.save(output_file)
    new_doc.close()
    doc.close()

    print(f"PDF particionado salvo em: {output_file}")
    return output_file
