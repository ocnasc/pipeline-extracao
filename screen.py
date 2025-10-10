import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pipeline_extracao import pipeline
from parcionar_pdf import parcionar
from s3_upload import enviar_para_s3
import os
import threading
import logging

# Initialize basic logging for the UI process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------
def executar():
    try:
        acao = var_acao.get()

        if acao == 1:  # Particionar PDF
            sectionname = entry_section.get().strip()
            path_manual_bruto = entry_pdf_bruto.get().strip()
            
            if not path_manual_bruto:
                messagebox.showwarning("Atenção", "Selecione o arquivo PDF bruto.")
                return
            
            if not sectionname:
                messagebox.showwarning("Atenção", "Digite o nome da seção.")
                return
            
            try:
                first_page = int(entry_first.get())
                last_page = int(entry_last.get())
                
                if first_page > last_page:
                    messagebox.showerror("Erro", "A primeira página deve ser menor ou igual à última.")
                    return
                
                pages = [first_page, last_page]
            except ValueError:
                messagebox.showerror("Erro", "As páginas devem ser números inteiros.")
                return

            btn_executar.config(state="disabled")
            status_label.config(text="⏳ Particionando PDF...", foreground="#0066cc")

            def run_particionar():
                try:
                    destino = parcionar(pages, sectionname, path_manual_bruto)
                    logger.info(f"PDF particionado em: {destino}")
                    root.after(0, lambda: messagebox.showinfo("✓ Sucesso", f"PDF particionado!\nSeção '{sectionname}' gerada com sucesso."))
                except Exception as e:
                    logger.error(f"Erro ao particionar: {e}")
                    root.after(0, lambda e=e: messagebox.showerror("Erro", f"Erro ao particionar: {str(e)}"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_particionar, daemon=True).start()

        elif acao == 2:  # Processar pipeline
            path_pdfs_parcionados = entry_pdfs_parcionados.get().strip()
            file_choice = combo_files.get()
            
            if not path_pdfs_parcionados:
                messagebox.showwarning("Atenção", "Selecione a pasta com os PDFs particionados.")
                return
            
            if not file_choice:
                messagebox.showwarning("Atenção", "Selecione um PDF para processar.")
                return

            btn_executar.config(state="disabled")
            status_label.config(text=f"⏳ Processando '{file_choice}'...", foreground="#0066cc")

            def run_pipeline():
                try:
                    pipeline(path_pdfs_parcionados, file_choice)
                    root.after(0, lambda: messagebox.showinfo("✓ Sucesso", f"Pipeline concluído!\nArquivo '{file_choice}' processado com sucesso."))
                except Exception as e:
                    logger.error(f"Erro no pipeline: {e}")
                    root.after(0, lambda e=e: messagebox.showerror("Erro", f"Erro no pipeline: {str(e)}"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_pipeline, daemon=True).start()

        elif acao == 3:  # Upload para S3
            file_choice = combo_files_s3.get().strip()
            s3_folder = entry_s3_folder.get().strip()
            filename_override = entry_filename.get().strip()
            pasta_local = entry_pasta_json.get().strip()

            if not pasta_local:
                messagebox.showwarning("Atenção", "Selecione a pasta local com os arquivos JSON.")
                return

            if not file_choice:
                messagebox.showwarning("Atenção", "Selecione um arquivo para enviar.")
                return

            filename = filename_override if filename_override else file_choice
            if not filename:
                messagebox.showerror("Erro", "Nome do arquivo no S3 não pode ficar vazio.")
                return

            # monta a key final
            if s3_folder:
                folder_clean = s3_folder.strip().strip("/")
                key = f"{folder_clean}/{filename}"
            else:
                key = filename

            filepath = os.path.join(pasta_local, file_choice)

            if not os.path.isfile(filepath):
                messagebox.showerror("Erro", f"Arquivo não encontrado: {filepath}")
                return

            btn_executar.config(state="disabled")
            status_label.config(text=f"⏳ Enviando para S3: {filename}...", foreground="#0066cc")

            def run_upload():
                try:
                    destino = enviar_para_s3(filepath, key)
                    root.after(0, lambda: messagebox.showinfo("✓ Sucesso", f"Arquivo enviado com sucesso!\n\n{destino}"))
                except Exception as e:
                    logger.error(f"Erro ao enviar para S3: {e}")
                    root.after(0, lambda e=e: messagebox.showerror("Erro", f"Erro ao enviar: {str(e)}"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_upload, daemon=True).start()

        else:
            messagebox.showerror("Erro", f"Ação inválida: {acao}")

    except Exception as e:
        messagebox.showerror("Erro", str(e))


def escolher_pdf():
    filename = filedialog.askopenfilename(
        title="Selecione o PDF Bruto",
        filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
    )
    if filename:
        entry_pdf_bruto.delete(0, "end")
        entry_pdf_bruto.insert(0, filename)


def escolher_pasta():
    folder = filedialog.askdirectory(title="Selecione a Pasta com PDFs Particionados")
    if folder:
        entry_pdfs_parcionados.delete(0, "end")
        entry_pdfs_parcionados.insert(0, folder)
        atualizar_lista_pdfs(folder)


def escolher_pasta_json():
    folder = filedialog.askdirectory(title="Selecione a Pasta com Arquivos JSON")
    if folder:
        entry_pasta_json.delete(0, "end")
        entry_pasta_json.insert(0, folder)
        atualizar_lista_json()


def atualizar_lista_pdfs(folder):
    combo_files.set("")
    combo_files["values"] = []
    if folder and os.path.isdir(folder):
        files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        combo_files["values"] = files
        if files:
            combo_files.current(0)


def atualizar_lista_json():
    combo_files_s3.set("")
    combo_files_s3["values"] = []
    folder = entry_pasta_json.get().strip()
    
    if folder and os.path.isdir(folder):
        files = [f for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(".json")]
        combo_files_s3["values"] = files
        
        if files:
            combo_files_s3.set(files[0])
            entry_filename.delete(0, "end")
            entry_filename.insert(0, files[0])
        else:
            combo_files_s3.set("")
            entry_filename.delete(0, "end")
    else:
        messagebox.showwarning("Atenção", "Selecione uma pasta válida primeiro.")


def on_json_selected(event=None):
    selection = combo_files_s3.get().strip()
    if selection:
        entry_filename.delete(0, "end")
        entry_filename.insert(0, selection)


def mostrar_frame_acao():
    acao = var_acao.get()
    
    # Esconder todos
    frame_secao.pack_forget()
    frame_pdf.pack_forget()
    frame_pasta.pack_forget()
    frame_arquivos.pack_forget()
    frame_s3.pack_forget()

    # Mostrar de acordo com a ação
    if acao == 1:
        frame_pdf.pack(fill="x", padx=15, pady=8)
        frame_secao.pack(fill="x", padx=15, pady=8)
    elif acao == 2:
        frame_pasta.pack(fill="x", padx=15, pady=8)
        frame_arquivos.pack(fill="x", padx=15, pady=8)
    elif acao == 3:
        frame_s3.pack(fill="x", padx=15, pady=8)


# -------------------------------------------------------------------
# Interface principal
# -------------------------------------------------------------------
root = ttk.Window(themename="cosmo")
root.title("Pipeline PDF + S3")
root.state("zoomed")  # Inicia em tela cheia (maximizado)
root.resizable(True, True)

# Título
titulo = ttk.Label(root, text="🚀 Pipeline de Processamento PDF + S3", 
                   font=("Segoe UI", 16, "bold"))
titulo.pack(pady=(15, 10))

subtitulo = ttk.Label(root, text="Particione, processe e envie seus documentos para a nuvem", 
                      font=("Segoe UI", 9))
subtitulo.pack(pady=(0, 15))

# Separador
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=15, pady=5)

# Frame de Ação
frame_acao = ttk.Labelframe(root, text="📋 Selecione a Ação", padding=15)
frame_acao.pack(fill="x", padx=15, pady=12)

var_acao = ttk.IntVar(value=1)
ttk.Radiobutton(frame_acao, text="📄 Particionar PDF", 
                variable=var_acao, value=1, 
                command=mostrar_frame_acao,
                bootstyle="info").pack(anchor="w", pady=4)
ttk.Radiobutton(frame_acao, text="⚙️ Processar PDFs (Pipeline)", 
                variable=var_acao, value=2, 
                command=mostrar_frame_acao,
                bootstyle="info").pack(anchor="w", pady=4)
ttk.Radiobutton(frame_acao, text="☁️ Enviar para Amazon S3", 
                variable=var_acao, value=3, 
                command=mostrar_frame_acao,
                bootstyle="info").pack(anchor="w", pady=4)

# ========== AÇÃO 1: PARTICIONAR ==========
frame_pdf = ttk.Labelframe(root, text="📁 Selecione o PDF Bruto", padding=12)
frame_pdf_inner = ttk.Frame(frame_pdf)
frame_pdf_inner.pack(fill="x")
entry_pdf_bruto = ttk.Entry(frame_pdf_inner, width=50)
entry_pdf_bruto.pack(side="left", padx=(0, 8), fill="x", expand=True)
ttk.Button(frame_pdf_inner, text="📂 Procurar", 
           bootstyle="info-outline", 
           command=escolher_pdf).pack(side="left")

frame_secao = ttk.Labelframe(root, text="⚙️ Configurações de Particionamento", padding=12)

ttk.Label(frame_secao, text="Primeira página:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
entry_first = ttk.Entry(frame_secao, width=15)
entry_first.insert(0, "1")
entry_first.grid(row=0, column=1, sticky="w", pady=6)

ttk.Label(frame_secao, text="Última página:", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
entry_last = ttk.Entry(frame_secao, width=15)
entry_last.insert(0, "10")
entry_last.grid(row=1, column=1, sticky="w", pady=6)

ttk.Label(frame_secao, text="Nome da seção:", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
entry_section = ttk.Entry(frame_secao, width=30)
entry_section.grid(row=2, column=1, sticky="w", pady=6)

# ========== AÇÃO 2: PROCESSAR PIPELINE ==========
frame_pasta = ttk.Labelframe(root, text="📁 Pasta com PDFs Particionados", padding=12)
frame_pasta_inner = ttk.Frame(frame_pasta)
frame_pasta_inner.pack(fill="x")
entry_pdfs_parcionados = ttk.Entry(frame_pasta_inner, width=50)
entry_pdfs_parcionados.pack(side="left", padx=(0, 8), fill="x", expand=True)
ttk.Button(frame_pasta_inner, text="📂 Procurar", 
           bootstyle="info-outline", 
           command=escolher_pasta).pack(side="left")

frame_arquivos = ttk.Labelframe(root, text="📄 Selecione o PDF para Processar", padding=12)
combo_files = ttk.Combobox(frame_arquivos, width=50, state="readonly", font=("Segoe UI", 9))
combo_files.pack(fill="x", padx=5, pady=5)

# ========== AÇÃO 3: UPLOAD S3 ==========
frame_s3 = ttk.Labelframe(root, text="☁️ Configurações de Upload S3", padding=12)

ttk.Label(frame_s3, text="📁 Pasta local com JSONs:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
frame_pasta_json_inner = ttk.Frame(frame_s3)
frame_pasta_json_inner.grid(row=0, column=1, sticky="ew", pady=6)
frame_s3.columnconfigure(1, weight=1)

entry_pasta_json = ttk.Entry(frame_pasta_json_inner, width=35)
entry_pasta_json.pack(side="left", fill="x", expand=True, padx=(0, 8))
ttk.Button(frame_pasta_json_inner, text="📂 Procurar", 
           bootstyle="info-outline", 
           command=escolher_pasta_json).pack(side="left")

ttk.Label(frame_s3, text="📂 Pasta no S3 (bucket):", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
entry_s3_folder = ttk.Entry(frame_s3, width=45)
entry_s3_folder.grid(row=1, column=1, sticky="ew", pady=6)

ttk.Label(frame_s3, text="📄 Arquivo local:", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
combo_files_s3 = ttk.Combobox(frame_s3, width=45, state="readonly", font=("Segoe UI", 9))
combo_files_s3.grid(row=2, column=1, sticky="ew", pady=6)
combo_files_s3.bind("<<ComboboxSelected>>", on_json_selected)

ttk.Label(frame_s3, text="✏️ Nome no S3 (opcional):", font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=6, padx=(0, 10))
entry_filename = ttk.Entry(frame_s3, width=45)
entry_filename.grid(row=3, column=1, sticky="ew", pady=6)

# Separador antes do botão
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=15, pady=15)

# Botão executar
btn_executar = ttk.Button(root, text="▶️ Executar", 
                          bootstyle="success", 
                          command=executar,
                          width=20)
btn_executar.pack(pady=10)

# Status
status_label = ttk.Label(root, text="", anchor="center", font=("Segoe UI", 9, "italic"))
status_label.pack(pady=(5, 15))

# Rodapé
rodape = ttk.Label(root, text="Pipeline PDF + S3 | Versão 2.0", 
                   font=("Segoe UI", 8), foreground="gray")
rodape.pack(side="bottom", pady=10)

# Mostrar tela inicial
mostrar_frame_acao()

root.mainloop()