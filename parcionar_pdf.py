from pypdf import PdfReader, PdfWriter

first_page = 49  # <-- primeira página da seção
last_page = 56  # <-- última página da seção

section_name = "operation" # substituir pelo nome da seção

path = "./pdfs/brutos/user_manual.pdf" # <-- PDF BRUTO 

def parcionar(pages: list, sectionname:str, pathmanual:str) -> None:
    reader = PdfReader(pathmanual)
    writer = PdfWriter()
    first_page = pages[0]
    last_page = pages[1]
    for i in range(first_page-1, last_page):
        writer.add_page(reader.pages[i])

    pdf_name = sectionname.replace(" ", "_").lower() + ".pdf"
    destiny_path = f"./pdfs/parcionados/{pdf_name}"

    with open(destiny_path, "wb") as f:
        writer.write(f)

    print(f"{pdf_name} salvo com sucesso em {destiny_path}")
