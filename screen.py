import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pipeline_extracao import pipeline
from parcionar_pdf import parcionar
import os
import threading


# -------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------
def executar():
    try:
        acao = var_acao.get()

        if acao == 1:
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

        elif acao == 2:
            path_pdfs_parcionados = entry_pdfs_parcionados.get().strip()
            file_choice = combo_files.get()
            if not file_choice:
                messagebox.showwarning("Atenção", "Selecione um PDF para processar.")
                return

            # Desabilita botão e informa status
            btn_executar.config(state="disabled")
            status_label.config(text=f"Processando {file_choice} ... (aguarde)")

            # roda pipeline em thread para não travar a GUI
            def run_pipeline():
                try:
                    pipeline(path_pdfs_parcionados, file_choice)
                except Exception as e:
                    # precisa chamar GUI na thread principal
                    root.after(0, lambda: messagebox.showerror("Erro", str(e)))
                else:
                    root.after(0, lambda: messagebox.showinfo("Sucesso", f"Pipeline concluído para {file_choice}!"))
                finally:
                    root.after(0, lambda: btn_executar.config(state="normal"))
                    root.after(0, lambda: status_label.config(text=""))

            threading.Thread(target=run_pipeline, daemon=True).start()


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


def mostrar_frame_acao():
    acao = var_acao.get()
    if acao == 1:
        frame_secao.pack(fill="x", padx=10, pady=5)
        frame_pdf.pack(fill="x", padx=10, pady=5)
        frame_pasta.pack_forget()
        frame_arquivos.pack_forget()
    elif acao == 2:
        frame_secao.pack_forget()
        frame_pdf.pack_forget()
        frame_pasta.pack(fill="x", padx=10, pady=5)
        frame_arquivos.pack(fill="x", padx=10, pady=5)
        # Atualiza lista sempre que troca para ação 2
        pasta_atual = entry_pdfs_parcionados.get().strip()
        atualizar_lista_pdfs(pasta_atual)


# -------------------------------------------------------------------
# Interface principal
# -------------------------------------------------------------------
root = ttk.Window(themename="flatly")
root.title("Pipeline PDF")
root.geometry("600x500")

# Ação
frame_acao = ttk.Labelframe(root, text="Ação", padding=10)
frame_acao.pack(fill="x", padx=10, pady=5)

var_acao = ttk.IntVar(value=1)
ttk.Radiobutton(frame_acao, text="1 - Parcionar PDFs", variable=var_acao, value=1, command=mostrar_frame_acao).pack(anchor="w", pady=2)
ttk.Radiobutton(frame_acao, text="2 - Processar PDFs (Pipeline)", variable=var_acao, value=2, command=mostrar_frame_acao).pack(anchor="w", pady=2)

# Frame para ação 1
frame_secao = ttk.Labelframe(root, text="Parâmetros da Seção (para ação 1)", padding=10)
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

frame_pdf = ttk.Labelframe(root, text="PDF Bruto (para ação 1)", padding=10)
entry_pdf_bruto = ttk.Entry(frame_pdf, width=50)
entry_pdf_bruto.insert(0, "./pdfs/brutos/user_manual.pdf")
entry_pdf_bruto.pack(side="left", padx=5, pady=5, fill="x", expand=True)

ttk.Button(frame_pdf, text="Selecionar", bootstyle=SECONDARY, command=escolher_pdf).pack(side="left", padx=5)

# Frame para ação 2
frame_pasta = ttk.Labelframe(root, text="Pasta PDFs Parcionados (para ação 2)", padding=10)
entry_pdfs_parcionados = ttk.Entry(frame_pasta, width=50)
entry_pdfs_parcionados.insert(0, "./pdfs/parcionados")
entry_pdfs_parcionados.pack(side="left", padx=5, pady=5, fill="x", expand=True)

ttk.Button(frame_pasta, text="Selecionar", bootstyle=SECONDARY, command=escolher_pasta).pack(side="left", padx=5)

frame_arquivos = ttk.Labelframe(root, text="Escolha o PDF para processar", padding=10)
combo_files = ttk.Combobox(frame_arquivos, width=50, state="readonly")
combo_files.pack(fill="x", padx=5, pady=5)

# Botão executar
btn_executar = ttk.Button(root, text="Executar", bootstyle=SUCCESS, command=executar)
btn_executar.pack(pady=20)

status_label = ttk.Label(root, text="", anchor="center")
status_label.pack(pady=(0,10))

# Mostrar inicialmente frame da ação 1
mostrar_frame_acao()

# Carregar lista inicial de PDFs da pasta padrão
atualizar_lista_pdfs(entry_pdfs_parcionados.get().strip())

# Loop principal
root.mainloop()
