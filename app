import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import piexif
from datetime import datetime
import os
import io
import zipfile
import hashlib

# Suporte a imagens de iPhone (.HEIC)
from pillow_heif import register_heif_opener
register_heif_opener()

# Dependências do ReportLab para geração de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.set_page_config(page_title="Laboratório Virtual - Espectrofotometria UV-Vis", layout="wide")

st.title("🔬 Simulador de Espectrofotometria UV-Vis: Curva de Calibração")
st.write("Determine a concentração de uma amostra desconhecida utilizando a Lei de Beer-Lambert e Regressão Linear.")

# --- 1. IDENTIFICAÇÃO DO ESTUDANTE ---
st.sidebar.header("Identificação do Aluno")
nome_aluno = st.sidebar.text_input("Nome Completo:")
matricula_input = st.sidebar.text_input("Matrícula (apenas números):")

if not nome_aluno or not matricula_input or not matricula_input.isdigit():
    st.warning("⚠️ Preencha seu nome e matrícula na barra lateral para carregar seus dados experimentais.")
    st.stop()

matricula = int(matricula_input)
ultimos_2 = matricula % 100

# --- GERADOR DE DADOS EXPERIMENTAIS UNICOS ---
# Concentração real da amostra desconhecida individualizada (ex: entre 15.0 e 34.8 mg/L)
conc_desconhecida_real = round(15.0 + (ultimos_2 * 0.2), 2)

# Parâmetros reais da curva teórica: A = 0.025 * C + 0.010
slope_teorico = 0.025
intercept_teorico = 0.010

# Concentrações dos Padrões (mg/L)
concs_padrao = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])

# Adição de ruído pseudo-aleatório reprodutível baseado na matrícula
np.random.seed(matricula)
ruido_padroes = np.random.normal(0, 0.008, len(concs_padrao))
absorbancias_padrao = np.round(slope_teorico * concs_padrao + intercept_teorico + ruido_padroes, 3)
absorbancias_padrao[0] = max(0.0, absorbancias_padrao[0]) # Garante branco >= 0

# Absorbância da amostra desconhecida do aluno
ruido_amostra = np.random.normal(0, 0.005)
abs_amostra_aluno = round(slope_teorico * conc_desconhecida_real + intercept_teorico + ruido_amostra, 3)

# --- ETAPA 1: VARREDURA E ESPECTRO DE ABSORÇÃO ---
st.header("1. Seleção do Comprimento de Onda ($\lambda_{máx}$)")
st.write("Observe o espectro de varredura do analito para identificar o comprimento de onda de máxima absorção:")

# Gráfico da varredura espectral (Banda Gaussiana centrada em 520 nm)
wl = np.linspace(400, 700, 300)
abs_spectrum = 0.8 * np.exp(-((wl - 520) ** 2) / (2 * 25 ** 2)) + 0.02

fig_spec, ax_spec = plt.subplots(figsize=(7, 3))
ax_spec.plot(wl, abs_spectrum, color='purple', linewidth=2)
ax_spec.axvline(x=520, color='red', linestyle='--', label='$\lambda_{máx} = 520$ nm')
ax_spec.set_xlabel("Comprimento de Onda (nm)")
ax_spec.set_ylabel("Absorbância (A)")
ax_spec.set_title("Espectro de Absorção UV-Vis da Amostra")
ax_spec.legend()
ax_spec.grid(True, linestyle=':', alpha=0.6)

st.pyplot(fig_spec)
plt.close(fig_spec)

st.divider()

# --- ETAPA 2: DADOS DA CURVA DE CALIBRAÇÃO ---
st.header("2. Leituras das Soluções Padrão e Amostra Desconhecida")
st.write("Leituras de Absorbância realizadas em **$\lambda = 520$ nm** com cubeta de $1,0$ cm de caminho óptico:")

col_tab, col_amostra = st.columns([2, 1])

with col_tab:
    df_padroes = pd.DataFrame({
        "Solução": ["Branco", "Padrão 1", "Padrão 2", "Padrão 3", "Padrão 4", "Padrão 5"],
        "Concentração (mg/L)": concs_padrao,
        "Absorbância (A)": absorbancias_padrao
    })
    st.table(df_padroes)

with col_amostra:
    st.info(f"🧪 **Sua Amostra Desconhecida**\n\n**Absorbância Lida ($A_{{amostra}}$):** `{abs_amostra_aluno}`")
    st.caption("Valor exclusivo gerado para a sua matrícula.")

st.divider()

# --- ETAPA 3: UPLOAD DO MANUSCRITO DA REGRASSAO LINEAR ---
st.header("3. Tratamento Estatístico Manuscrito")
st.write("Construa a Curva de Calibração no papel milimetrado/caderno ou software, realizando os cálculos de:")
st.markdown("1. **Equação da Reta:** $A = a \cdot C + b$ (Coeficiente angular $a$ e linear $b$)\n2. **Coeficiente de Determinação ($R^2$)**\n3. **Interpolação da Concentração Desconhecida ($C_{desc}$)**")

file_manuscrito = st.file_uploader("Envie a foto do seu gráfico/cálculos manuscritos:", type=["jpg", "jpeg", "png", "heic"], key="up_uvvis")

if file_manuscrito:
    bytes_m = file_manuscrito.getvalue()
    hash_m = hashlib.md5(bytes_m).hexdigest()
    img_m = Image.open(file_manuscrito)
    
    st.image(img_m, caption="Manuscrito Registrado", width=380)
    st.divider()

    # --- ETAPA 4: TRANSCRIÇÃO DOS RESULTADOS ---
    st.header("4. Transcrição dos Resultados")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        slope_aluno = st.number_input("Inclinação / Coef. Angular ($a$):", format="%.5f")
    with c2:
        intercept_aluno = st.number_input("Intercepto / Coef. Linear ($b$):", format="%.5f")
    with c3:
        r2_aluno = st.number_input("Coeficiente de Determinação ($R^2$):", format="%.4f")
    with c4:
        conc_aluno = st.number_input("Concentração Calculada ($mg/L$):", format="%.2f")

    # --- GERADOR DE RELATÓRIO PDF ---
    def gerar_pdf_uvvis(nome, mat, abs_amostra, slope, intercept, r2, conc_calc, file_script):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("<b>Relatório de Espectrofotometria UV-Vis (Lei de Beer)</b>", styles['Title']))
        elements.append(Spacer(1, 10))
        
        info = f"<b>Aluno:</b> {nome}<br/><b>Matrícula:</b> {mat}<br/><b>Data/Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        elements.append(Paragraph(info, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Tabela dos padrões no PDF
        data_pdf = [["Solução", "Conc. (mg/L)", "Absorbância (A)"]]
        for _, row in df_padroes.iterrows():
            data_pdf.append([str(row["Solução"]), str(row["Concentração (mg/L)"]), str(row["Absorbância (A)"])])
        
        t = Table(data_pdf, colWidths=[120, 120, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

        resumo = f"""
        <b>Absorbância da Amostra:</b> {abs_amostra}<br/>
        <b>Equação Transcrita pelo Aluno:</b> A = {slope} &middot; C + {intercept}<br/>
        <b>R<sup>2</sup>:</b> {r2} | <b>Concentração Calculada:</b> {conc_calc} mg/L
        """
        elements.append(Paragraph(resumo, styles['Normal']))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("<b>Gráfico e Resolução Manuscrita:</b>", styles['Heading2']))
        elements.append(Spacer(1, 5))
        
        img_m_pdf = Image.open(file_script).convert("RGB")
        img_m_pdf.thumbnail((400, 400))
        temp_path = f"temp_uvvis_{mat}.jpg"
        img_m_pdf.save(temp_path)
        
        elements.append(RLImage(temp_path, width=320, height=320))

        doc.build(elements)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        buffer.seek(0)
        return buffer.getvalue()

    # --- SUBMISSÃO FINAL ---
    if st.button("🚀 Enviar Relatório de UV-Vis"):
        pdf_bytes = gerar_pdf_uvvis(
            nome_aluno, matricula, abs_amostra_aluno,
            slope_aluno, intercept_aluno, r2_aluno, conc_aluno, file_manuscrito
        )
        
        os.makedirs("relatorios_uvvis", exist_ok=True)
        pdf_path = f"relatorios_uvvis/{nome_aluno.replace(' ', '_')}_{matricula}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        registro = {
            "Nome": nome_aluno.strip().title(),
            "Matricula": matricula,
            "DataEnvio": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "Abs_Amostra": abs_amostra_aluno,
            "Conc_Real_Gabarito": conc_desconhecida_real,
            "Slope_Aluno": slope_aluno,
            "Intercept_Aluno": intercept_aluno,
            "R2_Aluno": r2_aluno,
            "Conc_Aluno": conc_aluno,
            "Caminho_PDF": pdf_path
        }

        csv_file = "respostas_uvvis.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
        else:
            df = pd.DataFrame([registro])

        df.sort_values(by="Nome", ascending=True).to_csv(csv_file, index=False)
        st.success("🎉 Atividade de Espectrofotometria enviada com sucesso! O relatório em PDF foi salvo.")

# --- PAINEL DO PROFESSOR ---
st.sidebar.write("---")
if st.sidebar.checkbox("🔒 Acesso do Professor"):
    senha = st.sidebar.text_input("Senha de Acesso:", type="password")
    if senha == "prof123":
        st.header("📊 Painel do Professor - Respostas UV-Vis")
        
        csv_file = "respostas_uvvis.csv"
        if os.path.exists(csv_file):
            df_prof = pd.read_csv(csv_file)
            df_prof["Erro_Relativo_(%)"] = np.round(np.abs((df_prof["Conc_Aluno"] - df_prof["Conc_Real_Gabarito"]) / df_prof["Conc_Real_Gabarito"]) * 100, 2)
            
            st.subheader("Resultados Consolidados (Ordem Alfabética)")
            st.dataframe(df_prof)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                csv_data = df_prof.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar Planilha CSV de UV-Vis",
                    data=csv_data,
                    file_name="respostas_uvvis_ordenadas.csv",
                    mime="text/csv"
                )
            with col_d2:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for root, dirs, files in os.walk("relatorios_uvvis"):
                        for file in files:
                            zf.write(os.path.join(root, file), file)
                zip_buffer.seek(0)
                st.download_button(
                    label="📦 Baixar Todos os PDFs de UV-Vis (ZIP)",
                    data=zip_buffer,
                    file_name="relatorios_uvvis.zip",
                    mime="application/zip"
                )
        else:
            st.info("Nenhuma submissão registrada ainda.")
    elif senha:
        st.sidebar.error("Senha incorreta.")
