from pipeline_extracao import pipeline
from parcionar_pdf import parcionar

'''

Ação:

1. parcionar pdfs:
    pdf bruto (manual) -> pdf parcionado (seção)

2. processar pdfs:
    pdf parcionado (seção) -> json_bronze (seção)

'''

acao = 1

first_page = 49  # <-- primeira página da seção
last_page = 56  # <-- última página da seção
pages = [first_page, last_page]
sectionname = "operation" # substituir pelo nome da seção
path_manual_bruto = "./pdfs/brutos/user_manual.pdf" # <-- PDF BRUTO 
path_pdfs_parcionados = "./pdfs/parcionados"

if acao == 1:
    parcionar(pages,sectionname,path_manual_bruto)
elif acao == 2:
    pipeline(path_pdfs_parcionados)
else:
    raise Exception(f"Erro: {acao} não é uma ação válida, apenas 1 ou 2.")
