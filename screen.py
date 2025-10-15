import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pipeline_extracao import pipeline
from parcionar_pdf import parcionar
from s3_upload import enviar_para_s3
import os
import threading
from pathlib import Path
import shutil

# -------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------
def executar():
    try:
        # Verificação obrigatória dos campos iniciais
        serial_number = entry_serial.get().strip()
        manual_name = entry_manual.get().strip()
        sectionname = entry_section.get().strip()

        if not serial_number or not manual_name or not sectionname:
            messagebox.showerror("Erro", "Preencha Serial Number, Nome do Manual e Nome da Seção antes de continuar.")
            return

        acao = var_acao.get()

        if acao == 1:  # Particionar PDF
            path_manual_bruto = entry_pdf_bruto.get().strip()

            if not path_manual_bruto:
                messagebox.showerror("Erro", "Selecione o PDF bruto antes de continuar.")
                return

            try:
                first_page = int(entry_first.get())
                last_page = int(entry_last.get())
                pages = [first_page, last_page]
            except ValueError:
                messagebox.showerror("Erro", "As páginas devem ser números inteiros.")
                return

            # ------------------ Nova lógica ------------------

            user_pdf_path = Path(path_manual_bruto)
            base_path = user_pdf_path.parent


            # criar a pasta parcionados
            parcionados_dir = Path(base_path) / "PDFs parcionados"
            parcionados_dir.mkdir(parents=True, exist_ok=True)

            # chama a função de particionar PDF usando o caminho do bruto copiado
            parcionar(pages, sectionname, str(user_pdf_path), str(parcionados_dir))
            messagebox.showinfo("Sucesso", f"PDF particionado: seção '{sectionname}' gerada!")

            # opcional: você pode já preparar o filename para pipeline
            filename = f"{serial_number}_{manual_name}_{sectionname}"
            # pipeline(base_path, filename, selected_file=dest_bruto.name)


        elif acao == 2:  # Processar pipeline

            path_pdfs_parcionados = entry_pdfs_parcionados.get().strip()
            file_choice = combo_files.get()

            base_path = Path(path_pdfs_parcionados).parent

            diretorios = [
                Path(base_path) / "results" / "raw",
                Path(base_path) / "results" / "silver",
                Path(base_path) / "results" / "gold",
                Path(base_path) / "results" / "upload"
            ]

            for d in diretorios:
                d.mkdir(parents=True, exist_ok=True)
                print(f"Diretório verificado/criado: {d}")

            if not path_pdfs_parcionados:
                messagebox.showerror("Erro", "Selecione a pasta de PDFs particionados.")
                return
            if not file_choice:
                messagebox.showwarning("Atenção", "Selecione um PDF para processar.")
                return

            # 🔹 Cria o nome concatenado
            filename = f"{serial_number}_{manual_name}_{sectionname}"

            btn_executar.config(state="disabled")
            status_label.config(text=f"Processando {file_choice} ... (aguarde)")

            def run_pipeline():
                try:
                    # 🔹 Passa o filename para a função pipeline
                    pipeline(base_path, filename, file_choice)
                except Exception as e:
                    root.after(0, lambda e=e: messagebox.showerror("Erro", str(e)))
                else:
                    root.after(0, lambda: messagebox.showinfo(
                        "Sucesso", f"Pipeline concluído para {file_choice}!\nArquivo: {filename}"
                    ))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))


            threading.Thread(target=run_pipeline, daemon=True).start()

        elif acao == 3:  # Upload para S3
            file_choice = combo_files_s3.get().strip()
            s3_folder = entry_s3_folder.get().strip()
            filename_override = entry_filename.get().strip()

            if not file_choice:
                messagebox.showerror("Erro", "Selecione um arquivo local para enviar.")
                return

            filename = filename_override if filename_override else os.path.basename(file_choice)
            if not filename:
                messagebox.showerror("Erro", "Nome do arquivo no S3 não pode ficar vazio.")
                return

            key = f"{s3_folder.strip().strip('/')}/{filename}" if s3_folder else filename

            if not os.path.isfile(file_choice):
                messagebox.showerror("Erro", f"Arquivo local não encontrado: {file_choice}")
                return

            btn_executar.config(state="disabled")
            status_label.config(text=f"Enviando {file_choice} → s3://.../{key} ... (aguarde)")

            def run_upload():
                try:
                    destino = enviar_para_s3(file_choice, key)
                except Exception as e:
                    root.after(0, lambda e=e: messagebox.showerror("Erro", str(e)))
                else:
                    root.after(0, lambda: messagebox.showinfo("Sucesso", f"Arquivo enviado para {destino}"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_upload, daemon=True).start()

        else:
            messagebox.showerror("Erro", f"Ação inválida: {acao}")

    except Exception as e:
        messagebox.showerror("Erro", str(e))


def escolher_pdf():
    filename = filedialog.askopenfilename(filetypes=[("Arquivos PDF", "*.pdf")])
    if filename:
        entry_pdf_bruto.delete(0, "end")
        entry_pdf_bruto.insert(0, filename)

        manual_name = os.path.splitext(os.path.basename(filename))[0]
        entry_manual.delete(0, "end")
        entry_manual.insert(0, manual_name)



def escolher_pasta():
    folder = filedialog.askdirectory()
    if folder:
        entry_pdfs_parcionados.delete(0, "end")
        entry_pdfs_parcionados.insert(0, folder)
        atualizar_lista_pdfs(folder)


def atualizar_lista_pdfs(folder):
    combo_files.set("")
    combo_files["values"] = []
    if os.path.isdir(folder):
        files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        combo_files["values"] = files


def escolher_json():
    filename = filedialog.askopenfilename(filetypes=[("Arquivos JSON", "*.json")])
    if filename:
        combo_files_s3.set(filename)
        entry_filename.delete(0, "end")
        entry_filename.insert(0, os.path.basename(filename))


def mostrar_frame_acao():
    acao = var_acao.get()
    frame_secao.pack_forget()
    frame_pdf.pack_forget()
    frame_pasta.pack_forget()
    frame_arquivos.pack_forget()
    frame_s3.pack_forget()

    if acao == 1:
        frame_secao.pack(fill="x", padx=10, pady=5)
        frame_pdf.pack(fill="x", padx=10, pady=5)
    elif acao == 2:
        frame_pasta.pack(fill="x", padx=10, pady=5)
        frame_arquivos.pack(fill="x", padx=10, pady=5)
    elif acao == 3:
        frame_s3.pack(fill="x", padx=10, pady=5)

# -------------------------------------------------------------------
# Interface principal
# -------------------------------------------------------------------
root = ttk.Window(themename="flatly")
root.title("Pipeline PDF + S3")
root.geometry("700x700")

# ---------------------- Campos obrigatórios iniciais ----------------------
frame_info = ttk.Labelframe(root, text="Informações Iniciais", padding=10)
frame_info.pack(fill="x", padx=10, pady=10)

ttk.Label(frame_info, text="Serial Number:").grid(row=0, column=0, sticky="w", pady=4)
entry_serial = ttk.Entry(frame_info, width=30)
entry_serial.grid(row=0, column=1, padx=5, pady=4)





ttk.Label(frame_info, text="Nome do Manual:").grid(row=1, column=0, sticky="w", pady=4)
entry_manual = ttk.Entry(frame_info, width=30)
entry_manual.grid(row=1, column=1, padx=5, pady=4)

# ---------------------- Escolha da ação ----------------------
frame_acao = ttk.Labelframe(root, text="Ação", padding=10)
frame_acao.pack(fill="x", padx=10, pady=8)

var_acao = ttk.IntVar(value=1)
ttk.Radiobutton(frame_acao, text="1 - Particionar PDFs", variable=var_acao, value=1, command=mostrar_frame_acao).pack(anchor="w", pady=2)
ttk.Radiobutton(frame_acao, text="2 - Processar PDFs (Pipeline)", variable=var_acao, value=2, command=mostrar_frame_acao).pack(anchor="w", pady=2)
ttk.Radiobutton(frame_acao, text="3 - Enviar arquivos para Amazon S3", variable=var_acao, value=3, command=mostrar_frame_acao).pack(anchor="w", pady=2)

# ---------------------- Ação 1 ----------------------
frame_secao = ttk.Labelframe(root, text="Parâmetros da Seção (ação 1)", padding=10)
ttk.Label(frame_secao, text="Primeira página:").grid(row=0, column=0, sticky="w", pady=2)
entry_first = ttk.Entry(frame_secao, width=10)
entry_first.grid(row=0, column=1, padx=5, pady=2)

ttk.Label(frame_secao, text="Última página:").grid(row=1, column=0, sticky="w", pady=2)
entry_last = ttk.Entry(frame_secao, width=10)
entry_last.grid(row=1, column=1, padx=5, pady=2)

ttk.Label(frame_secao, text="Nome da seção:").grid(row=2, column=0, sticky="w", pady=2)
entry_section = ttk.Entry(frame_secao, width=20)
entry_section.grid(row=2, column=1, padx=5, pady=2)

frame_pdf = ttk.Labelframe(root, text="PDF Bruto (ação 1)", padding=10)
entry_pdf_bruto = ttk.Entry(frame_pdf, width=50)
entry_pdf_bruto.pack(side="left", padx=5, pady=5, fill="x", expand=True)
ttk.Button(frame_pdf, text="Selecionar", bootstyle=SECONDARY, command=escolher_pdf).pack(side="left", padx=5)

# ---------------------- Ação 2 ----------------------
frame_pasta = ttk.Labelframe(root, text="Pasta PDFs Parcionados", padding=10)
entry_pdfs_parcionados = ttk.Entry(frame_pasta, width=50)
entry_pdfs_parcionados.pack(side="left", padx=5, pady=5, fill="x", expand=True)
ttk.Button(frame_pasta, text="Selecionar", bootstyle=SECONDARY, command=escolher_pasta).pack(side="left", padx=5)

frame_arquivos = ttk.Labelframe(root, text="Escolha o PDF para processar (ação 2)", padding=10)
combo_files = ttk.Combobox(frame_arquivos, width=50, state="readonly")
combo_files.pack(fill="x", padx=5, pady=5)

# ---------------------- Ação 3 ----------------------
frame_s3 = ttk.Labelframe(root, text="Envio para Amazon S3 (ação 3)", padding=10)
ttk.Label(frame_s3, text="Pasta no S3 (dentro do bucket):").grid(row=0, column=0, sticky="w", pady=4)
entry_s3_folder = ttk.Entry(frame_s3, width=48)
entry_s3_folder.grid(row=0, column=1, padx=5, pady=4)

ttk.Label(frame_s3, text="Arquivo local (JSON):").grid(row=1, column=0, sticky="w", pady=4)
combo_files_s3 = ttk.Combobox(frame_s3, width=48, state="readonly")
combo_files_s3.grid(row=1, column=1, padx=5, pady=4)
ttk.Button(frame_s3, text="Selecionar arquivo", bootstyle=SECONDARY, command=escolher_json).grid(row=1, column=2, padx=5)

ttk.Label(frame_s3, text="Nome no S3 (arquivo):").grid(row=2, column=0, sticky="w", pady=4)
entry_filename = ttk.Entry(frame_s3, width=48)
entry_filename.grid(row=2, column=1, padx=5, pady=4)

# ---------------------- Botão executar ----------------------
btn_executar = ttk.Button(root, text="Executar", bootstyle=SUCCESS, command=executar)
btn_executar.pack(pady=18)

status_label = ttk.Label(root, text="", anchor="center")
status_label.pack(pady=(0, 12))




entry_serial.insert(0, "10317674") ## TESTE !!!! apagar depois
entry_first.insert(0, "51") ## TESTE !!!! apagar depois
entry_last.insert(0, "56") ## TESTE !!!! apagar depois
entry_section.insert(0, "installation") ## TESTE !!!! apagar depois





mostrar_frame_acao()
root.mainloop()
