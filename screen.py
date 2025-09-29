import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pipeline_extracao import pipeline
from parcionar_pdf import parcionar
from s3_upload import enviar_para_s3
import os
import threading

# -------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------
def executar():
    try:
        acao = var_acao.get()

        if acao == 1:  # Particionar PDF
            sectionname = entry_section.get().strip()
            path_manual_bruto = entry_pdf_bruto.get().strip()
            try:
                first_page = int(entry_first.get())
                last_page = int(entry_last.get())
                pages = [first_page, last_page]
            except ValueError:
                messagebox.showerror("Erro", "As páginas devem ser números inteiros.")
                return

            parcionar(pages, sectionname, path_manual_bruto)
            messagebox.showinfo("Sucesso", f"PDF particionado: seção '{sectionname}' gerada!")

        elif acao == 2:  # Processar pipeline
            path_pdfs_parcionados = entry_pdfs_parcionados.get().strip()
            file_choice = combo_files.get()
            if not file_choice:
                messagebox.showwarning("Atenção", "Selecione um PDF para processar.")
                return

            btn_executar.config(state="disabled")
            status_label.config(text=f"Processando {file_choice} ... (aguarde)")

            def run_pipeline():
                try:
                    pipeline(path_pdfs_parcionados, file_choice)
                except Exception as e:
                    root.after(0, lambda e=e: messagebox.showerror("Erro", str(e)))
                else:
                    root.after(0, lambda: messagebox.showinfo("Sucesso", f"Pipeline concluído para {file_choice}!"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_pipeline, daemon=True).start()

        elif acao == 3:  # Upload para S3
            file_choice = combo_files_s3.get().strip()
            s3_folder = entry_s3_folder.get().strip()
            filename_override = entry_filename.get().strip()

            if not file_choice:
                messagebox.showerror("Erro", "Selecione um arquivo local para enviar (../assets/json_results/gold).")
                return

            # se não informou filename_override usa o nome original do arquivo selecionado
            filename = filename_override if filename_override else file_choice
            if not filename:
                messagebox.showerror("Erro", "Nome do arquivo no S3 não pode ficar vazio.")
                return

            # monta a key final (pasta/key + nome)
            if s3_folder:
                # remove barras finais/iniciais para evitar duplicação
                folder_clean = s3_folder.strip().strip("/")
                key = f"{folder_clean}/{filename}"
            else:
                key = filename

            folder_local = "../assets/json_results/gold"
            filepath = os.path.join(folder_local, file_choice)

            if not os.path.isfile(filepath):
                messagebox.showerror("Erro", f"Arquivo local não encontrado: {filepath}")
                return

            # roda upload em thread
            btn_executar.config(state="disabled")
            status_label.config(text=f"Enviando {file_choice} → s3://.../{key} ... (aguarde)")

            def run_upload():
                try:
                    destino = enviar_para_s3(filepath, key)
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


def atualizar_lista_json():
    combo_files_s3.set("")
    combo_files_s3["values"] = []
    folder = "../assets/json_results/gold"
    if os.path.isdir(folder):
        # lista apenas arquivos regulares; filtra por extensões comuns (.json)
        files = [f for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(".json")]
        combo_files_s3["values"] = files
        # se houver pelo menos um arquivo, seleciona o primeiro e preenche o nome default
        if files:
            combo_files_s3.set(files[0])
            entry_filename.delete(0, "end")
            entry_filename.insert(0, files[0])
        else:
            combo_files_s3.set("")
            entry_filename.delete(0, "end")


def on_json_selected(event=None):
    # quando o usuário seleciona outro arquivo, preenche o campo nome com o nome original
    selection = combo_files_s3.get().strip()
    if selection:
        entry_filename.delete(0, "end")
        entry_filename.insert(0, selection)


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
        atualizar_lista_pdfs(entry_pdfs_parcionados.get().strip())
    elif acao == 3:
        frame_s3.pack(fill="x", padx=10, pady=5)
        atualizar_lista_json()


# -------------------------------------------------------------------
# Interface principal
# -------------------------------------------------------------------
root = ttk.Window(themename="flatly")
root.title("Pipeline PDF + S3")
root.geometry("680x640")

# Ação
frame_acao = ttk.Labelframe(root, text="Ação", padding=10)
frame_acao.pack(fill="x", padx=10, pady=8)

var_acao = ttk.IntVar(value=1)
ttk.Radiobutton(frame_acao, text="1 - Parcionar PDFs", variable=var_acao, value=1, command=mostrar_frame_acao).pack(anchor="w", pady=2)
ttk.Radiobutton(frame_acao, text="2 - Processar PDFs (Pipeline)", variable=var_acao, value=2, command=mostrar_frame_acao).pack(anchor="w", pady=2)
ttk.Radiobutton(frame_acao, text="3 - Enviar arquivos para Amazon S3", variable=var_acao, value=3, command=mostrar_frame_acao).pack(anchor="w", pady=2)

# Frame ação 1 (particionar)
frame_secao = ttk.Labelframe(root, text="Parâmetros da Seção (ação 1)", padding=10)
ttk.Label(frame_secao, text="Primeira página:").grid(row=0, column=0, sticky="w", pady=2)
entry_first = ttk.Entry(frame_secao, width=10)
entry_first.insert(0, "49")
entry_first.grid(row=0, column=1, padx=5, pady=2)

ttk.Label(frame_secao, text="Última página:").grid(row=1, column=0, sticky="w", pady=2)
entry_last = ttk.Entry(frame_secao, width=10)
entry_last.insert(0, "56")
entry_last.grid(row=1, column=1, padx=5, pady=2)

ttk.Label(frame_secao, text="Nome da seção:").grid(row=2, column=0, sticky="w", pady=2)
entry_section = ttk.Entry(frame_secao, width=20)
entry_section.insert(0, "operation")
entry_section.grid(row=2, column=1, padx=5, pady=2)

frame_pdf = ttk.Labelframe(root, text="PDF Bruto (ação 1)", padding=10)
entry_pdf_bruto = ttk.Entry(frame_pdf, width=50)
entry_pdf_bruto.insert(0, "./pdfs/brutos/user_manual.pdf")
entry_pdf_bruto.pack(side="left", padx=5, pady=5, fill="x", expand=True)
ttk.Button(frame_pdf, text="Selecionar", bootstyle=SECONDARY, command=escolher_pdf).pack(side="left", padx=5)

# Frame ação 2 (pipeline)
frame_pasta = ttk.Labelframe(root, text="Pasta PDFs Parcionados", padding=10)
entry_pdfs_parcionados = ttk.Entry(frame_pasta, width=50)
entry_pdfs_parcionados.insert(0, "./pdfs/parcionados")
entry_pdfs_parcionados.pack(side="left", padx=5, pady=5, fill="x", expand=True)
ttk.Button(frame_pasta, text="Selecionar", bootstyle=SECONDARY, command=escolher_pasta).pack(side="left", padx=5)

frame_arquivos = ttk.Labelframe(root, text="Escolha o PDF para processar (ação 2)", padding=10)
combo_files = ttk.Combobox(frame_arquivos, width=50, state="readonly")
combo_files.pack(fill="x", padx=5, pady=5)

# Frame ação 3 (S3)
frame_s3 = ttk.Labelframe(root, text="Envio para Amazon S3 (ação 3)", padding=10)

ttk.Label(frame_s3, text="Pasta no S3 (dentro do bucket) - ex: 'clientes/2023':").grid(row=0, column=0, sticky="w", pady=4)
entry_s3_folder = ttk.Entry(frame_s3, width=48)
entry_s3_folder.grid(row=0, column=1, padx=5, pady=4)

ttk.Label(frame_s3, text="Arquivo local (../assets/json_results/gold):").grid(row=1, column=0, sticky="w", pady=4)
combo_files_s3 = ttk.Combobox(frame_s3, width=48, state="readonly")
combo_files_s3.grid(row=1, column=1, padx=5, pady=4)
combo_files_s3.bind("<<ComboboxSelected>>", on_json_selected)

ttk.Label(frame_s3, text="Nome no S3 (arquivo) - deixe vazio para usar o original:").grid(row=2, column=0, sticky="w", pady=4)
entry_filename = ttk.Entry(frame_s3, width=48)
entry_filename.grid(row=2, column=1, padx=5, pady=4)

# Botão executar
btn_executar = ttk.Button(root, text="Executar", bootstyle=SUCCESS, command=executar)
btn_executar.pack(pady=18)

status_label = ttk.Label(root, text="", anchor="center")
status_label.pack(pady=(0,12))

# Mostrar tela inicial e carregar listas
mostrar_frame_acao()
atualizar_lista_pdfs(entry_pdfs_parcionados.get().strip())

root.mainloop()
