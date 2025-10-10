from pypdf import PdfReader, PdfWriter
import logging
import os
from pathlib import Path
from typing import List


logger = logging.getLogger(__name__)


def _validate_pages(pages: List[int]) -> None:
    if not pages or len(pages) != 2:
        raise ValueError("'pages' deve conter [primeira_pagina, ultima_pagina]")
    if not all(isinstance(p, int) for p in pages):
        raise ValueError("As páginas devem ser números inteiros")
    if pages[0] <= 0 or pages[1] <= 0:
        raise ValueError("Os números das páginas devem ser positivos")
    if pages[0] > pages[1]:
        raise ValueError("A primeira página deve ser menor ou igual à última")


def _ensure_output_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def parcionar(pages: list, sectionname: str, pathmanual: str) -> Path:
    """Recorta páginas de um PDF e salva como um novo arquivo.

    Args:
        pages: [primeira_pagina, ultima_pagina] (1-based)
        sectionname: nome da seção para compor o nome do arquivo
        pathmanual: caminho do PDF de origem

    Returns:
        Caminho do PDF gerado
    """
    _validate_pages(pages)

    source_path = Path(pathmanual)
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {source_path}")
    if not os.access(source_path, os.R_OK):
        raise PermissionError(f"Sem permissão de leitura: {source_path}")

    first_page = pages[0]
    last_page = pages[1]

    reader = PdfReader(str(source_path))
    writer = PdfWriter()

    total_pages = len(reader.pages)
    if last_page > total_pages:
        raise ValueError(
            f"'ultima_pagina' ({last_page}) excede o total de páginas ({total_pages})"
        )

    for i in range(first_page - 1, last_page):
        writer.add_page(reader.pages[i])

    pdf_name = sectionname.replace(" ", "_").lower() + ".pdf"
    output_dir = Path("../assets/pdfs/parcionados")
    _ensure_output_dir(output_dir)
    destiny_path = output_dir / pdf_name

    with open(destiny_path, "wb") as f:
        writer.write(f)

    logger.info(f"PDF gerado com sucesso: {destiny_path}")
    return destiny_path
