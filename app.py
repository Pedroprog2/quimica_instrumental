import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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

st.set_page_config(page_title="Laboratório Virtual 3D/2D - Espectrofotometria", layout="wide")

st.title("🧪 Laboratório Virtual: Espectrofotometria e Preparo de Soluções")
st.write("Opere o espectrofotômetro, prepare as diluições na bancada virtual e determine a concentração da sua amostra individual.")

# --- 1. IDENTIFICAÇÃO DO ESTUDANTE ---
st.sidebar.header("Identificação do Aluno")
nome_aluno = st.sidebar.text_input("Nome Completo:")
matricula_input = st.sidebar.text_input("Matrícula (apenas números):")

if not nome_aluno or not matricula_input or not matricula_input.isdigit():
    st.warning("⚠️ Preencha seu nome e matrícula na barra lateral para iniciar a bancada do laboratório.")
    st.stop()

matricula = int(matricula_input)
ultimos_2 = matricula % 100

# --- ESTADOS DA SESSÃO (PERSISTÊNCIA DE DADOS DO SIMULADOR) ---
if 'volume_balaum' not in st.session_state:
    st.session_state.volume_balaum = 0.0  # mL de solução + água no balão
if 'aliquota_estoque' not in st.session_state:
    st.session_state.aliquota_estoque = 0.0 # mL de Solução Mãe adicionada
if 'padroes_preparados' not in st.session_state:
    st.session_state.padroes_preparados = [] # Tabela de padrões criados pelo aluno

# Concentração da Solução Mãe
C_estoque = 100.0 # mg/L

# Concentração real da amostra individualizada baseada na matrícula
conc_amostra_gabarito = round(12.0 + (ultimos_2 * 0.25), 2)
abs_amostra_gabarito = round(0.022 * conc_amostra_gabarito + 0.012, 3)

# --- ABA 1: VARREDURA E AJUSTE DO COMPRIMENTO DE ONDA ---
st.header("1. Operação do Espectrofotômetro: Determinação de $\lambda_{máx}$")
st.write("Ajuste o botão do comprimento de onda no visor do equipamento e encontre a absorbância máxima para a amostra:")

col_equip, col_painel = st.columns([1, 1])

with col_equip:
    lambda_sel = st.slider("Ajuste do Comprimento de Onda ($\lambda$ em nm):", min_value=400, max_value=700, value=450, step=5)

# Equação Gaussiana para calcular a absorbância realista em tempo real
abs_dinamica = round(0.75 * np.exp(-((lambda_sel - 520) ** 2) / (2 * 28 ** 2)) + 0.015, 3)

def desenhar_espectrofotometro(lambda_val, abs_val):
    img = Image.new("RGBA", (350, 220), (230, 230, 235, 255))
    draw = ImageDraw.Draw(img)
    
    # Carcaça do Equipamento
    draw.rectangle([10, 10, 340, 210], outline=(80, 80, 90), fill=(210, 215, 220), width=3)
    # Compartimento de Cubetas (Tampa)
    draw.rectangle([30, 30, 110, 110], outline=(50, 50, 50), fill=(100, 100, 100), width=2)
    draw.text((38, 65), "CUBETA", fill=(255, 255, 255))
    
    # Visor Digital (Display LCD)
    draw.rectangle([140, 30, 320, 100], fill=(10, 40, 10), outline=(0, 0, 0), width=2)
    draw.text((150, 40), f"WL: {lambda_val} nm", fill=(50, 255, 50))
    draw.text((150, 65), f"ABS: {abs_val:.3f} A", fill=(50, 255, 50))
    
    # Botões Físicos
    draw.ellipse([160, 130, 190, 160], fill=(180, 50, 50)) # Power
    draw.ellipse([210, 130, 240, 160], fill=(70, 70, 70)) # Zero/Blank
    draw.ellipse([260, 130, 290, 160], fill=(70, 70, 70)) # Mode
    
    return img

with col_painel:
    st.image(desenhar_espectrofotometro(lambda_sel, abs_dinamica), caption="Visor Digital do Espectrofotômetro UV-Vis")
    if lambda_sel == 520:
        st.success("🎯 **Comprimento de onda ideal ($\lambda_{máx} = 520\text{ nm}$)** selecionado com sucesso!")
    else:
        st.info("💡 Varra o comprimento de onda até encontrar o valor mais alto de Absorbância (ABS).")

st.divider()

# --- ABA 2: BANCADA VIRTUAL DE PREPARO DE SOLUÇÕES (DILUIÇÃO) ---
st.header("2. Bancada Virtual de Diluição e Preparo dos Padrões")
st.write("Prepare suas soluções padrão no **Balão Volumétrico de 50 mL** a partir da **Solução Mãe (100 mg/L)**.")

col_bancada1, col_bancada2 = st.columns([1, 1])

with col_bancada1:
    st.subheader("Ações do Laboratório")
    
    # 1. Adicionar Alíquota do Estoque
    aliquota_add = st.number_input("Pipetar Alíquota da Solução Mãe (mL):", min_value=0.0, max_value=25.0, value=5.0, step=1.0)
    if st.button("🧪 Transferir Alíquota para o Balão"):
        if st.session_state.volume_balaum == 0:
            st.session_state.aliquota_estoque = aliquota_add
            st.session_state.volume_balaum = aliquota_add
            st.success(f"{aliquota_add} mL de Solução Mãe adicionados ao balão.")
        else:
            st.error("Lave o balão antes de iniciar um novo preparo!")

    # 2. Adicionar Água Destilada
    st.markdown("**Adicionar Água Destilada para Aferir o Menisco:**")
    c_água1, c_água2, c_água3 = st.columns(3)
    with c_água1:
        if st.button("➕ 10 mL Água"):
            st.session_state.volume_balaum += 10.0
    with c_água2:
        if st.button("➕ 1.0 mL Água"):
            st.session_state.volume_balaum += 1.0
    with c_água3:
        if st.button("💧 Gota a Gota (0.1 mL)"):
            st.session_state.volume_balaum = round(st.session_state.volume_balaum + 0.1, 2)

    if st.button("🧼 Lavar / Esvaziar Balão"):
        st.session_state.volume_balaum = 0.0
        st.session_state.aliquota_estoque = 0.0

# Desenho dinâmico do Balão Volumétrico
def desenhar_balao(vol_total):
    img = Image.new("RGBA", (250, 320), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Gargalo e Corpo do Balão (50 mL)
    silhueta = [(100, 20), (150, 20), (150, 140), (220, 250), (210, 290), (40, 290), (30, 250), (100, 140)]
    
    # Cor do líquido baseada na concentração (quanto mais concentrado, mais roxo)
    conc_atual = (st.session_state.aliquota_estoque * C_estoque) / max(vol_total, 1.0)
    int_cor = int(min(255, conc_atual * 2.5))
    cor_liq = (200 - int_cor//2, 50, 180 + int_cor//4, 200)

    # Nível do Líquido
    if vol_total > 0:
        # Mapeia 50 mL exatamente na linha do menisco (y = 100)
        y_nivel = max(30, 285 - int(vol_total * 3.7))
        draw.rectangle([42, y_nivel, 208, 288], fill=cor_liq)

    # Vidro do Balão
    draw.polygon(silhueta, outline=(60, 60, 60), width=3)
    # Linha do Traço de Aferição (Menisco 50 mL)
    draw.line([100, 100, 150, 100], fill=(255, 0, 0), width=2)
    draw.text((158, 93), "← Menisco 50 mL", fill=(255, 0, 0))
    
    return img

with col_bancada2:
    st.image(desenhar_balao(st.session_state.volume_balaum), caption="Balão Volumétrico de 50 mL")
    v_tot = st.session_state.volume_balaum
    st.write(f"**Volume atual no balão:** `{v_tot:.1f} / 50.0 mL`")
    
    # Validação do Menisco
    if abs(v_tot - 50.0) < 0.05:
        st.success("✨ **Perfeito! O menisco foi aferido exatamente em 50.0 mL!**")
        c_calc = round((st.session_state.aliquota_estoque * C_estoque) / 50.0, 2)
        st.info(f"Concentração da solução preparada: **{c_calc} mg/L**")
        
        if st.button("💾 Salvar Solução na Tabela de Padrões"):
            # Calcula absorbância da solução criada com leve ruído
            abs_padrao = round(0.022 * c_calc + 0.012 + np.random.normal(0, 0.004), 3)
            st.session_state.padroes_preparados.append({
                "Solução": f"Padrão {len(st.session_state.padroes_preparados) + 1}",
                "Alíquota (mL)": st.session_state.aliquota_estoque,
                "Concentração (mg/L)": c_calc,
                "Absorbância (A)": abs_padrao
            })
            st.success("Solução registrada!")
    elif v_tot > 50.0:
        st.error("❌ **Você passou do menisco!** A solução foi diluída além do volume do balão. Clique em 'Lavar / Esvaziar Balão' para tentar novamente.")

st.divider()

# --- ABA 3: LEITURA FINAL E TRANSCRIÇÃO ---
st.header("3. Leituras Registradas e Amostra Desconhecida")

if len(st.session_state.padroes_preparados) > 0:
    df_padroes = pd.DataFrame(st.session_state.padroes_preparados)
    st.subheader("Sua Tabela de Padrões Preparados")
    st.table(df_padroes)
else:
    st.warning("⚠️ Você ainda não preparou e salvou nenhuma solução padrão na bancada virtual acima.")

st.subheader("🧪 Sua Amostra Desconhecida")
st.info(f"**Absorbância Lida no Espectrofotômetro ($A_{{amostra}}$):** `{abs_amostra_gabarito}` (Valor exclusivo da sua matrícula)")

st.divider()

# --- ABA 4: CÁLCULOS E SUBMISSÃO DO MANUSCRITO ---
st.header("4. Resolução Manuscrita e Submissão")
st.write("Com os dados da sua tabela de padrões e da amostra desconhecida, construa a Curva de Calibração e envie seu manuscrito:")

file_manuscrito = st.file_uploader("Envie a foto dos cálculos manuscritos e do gráfico:", type=["jpg", "jpeg", "png", "heic"])

if file_manuscrito:
    img_m = Image.open(file_manuscrito)
    st.image(img_m, caption="Manuscrito Registrado", width=350)
    
    st.subheader("Transcrição dos Resultados Calculados")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        slope_aluno = st.number_input("Inclinação ($a$):", format="%.5f")
    with c2:
        intercept_aluno = st.number_input("Intercepto ($b$):", format="%.5f")
    with c3:
        r2_aluno = st.number_input("Coeficiente $R^2$:", format="%.4f")
    with c4:
        conc_aluno = st.number_input("Concentração Calculada ($mg/L$):", format="%.2f")

    # --- GERADOR DE PDF ---
    def gerar_pdf_simulador(nome, mat, df_p, abs_amostra, slope, intercept, r2, conc, file_script):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("<b>Relatório do Laboratório Virtual de Espectrofotometria</b>", styles['Title']))
        elements.append(Spacer(1, 10))
        
        info = f"<b>Aluno:</b> {nome}<br/><b>Matrícula:</b> {mat}<br/><b>Data/Hora:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        elements.append(Paragraph(info, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Tabela dos Padrões
        data_pdf = [["Solução", "Alíquota (mL)", "Conc. (mg/L)", "Absorbância (A)"]]
        for _, row in df_p.iterrows():
            data_pdf.append([str(row["Solução"]), str(row["Alíquota (mL)"]), str(row["Concentração (mg/L)"]), str(row["Absorbância (A)"])])
        
        t = Table(data_pdf, colWidths=[100, 100, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

        res = f"""
        <b>Absorbância da Amostra:</b> {abs_amostra}<br/>
        <b>Reta Calculada pelo Aluno:</b> A = {slope} &middot; C + {intercept}<br/>
        <b>R<sup>2</sup>:</b> {r2} | <b>Concentração Final Obtida:</b> {conc} mg/L
        """
        elements.append(Paragraph(res, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Inserção da foto do manuscrito
        img_m_pdf = Image.open(file_script).convert("RGB")
        img_m_pdf.thumbnail((400, 400))
        temp_path = f"temp_lab_{mat}.jpg"
        img_m_pdf.save(temp_path)
        
        elements.append(RLImage(temp_path, width=320, height=320))

        doc.build(elements)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        buffer.seek(0)
        return buffer.getvalue()

    if st.button("🚀 Finalizar e Enviar Atividade do Laboratório Virtual"):
        if len(st.session_state.padroes_preparados) < 3:
            st.error("Prepare pelo menos 3 soluções padrão antes de enviar!")
        else:
            pdf_bytes = gerar_pdf_simulador(
                nome_aluno, matricula, pd.DataFrame(st.session_state.padroes_preparados),
                abs_amostra_gabarito, slope_aluno, intercept_aluno, r2_aluno, conc_aluno, file_manuscrito
            )
            
            os.makedirs("relatorios_lab", exist_ok=True)
            pdf_path = f"relatorios_lab/{nome_aluno.replace(' ', '_')}_{matricula}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            registro = {
                "Nome": nome_aluno.strip().title(),
                "Matricula": matricula,
                "DataEnvio": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Abs_Amostra": abs_amostra_gabarito,
                "Conc_Real_Gabarito": conc_amostra_gabarito,
                "Slope_Aluno": slope_aluno,
                "Intercept_Aluno": intercept_aluno,
                "R2_Aluno": r2_aluno,
                "Conc_Aluno": conc_aluno,
                "PDF": pdf_path
            }

            csv_file = "respostas_lab_virtual.csv"
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
            else:
                df = pd.DataFrame([registro])

            df.sort_values(by="Nome", ascending=True).to_csv(csv_file, index=False)
            st.success("🎉 Atividade do Laboratório Virtual enviada com sucesso!")

# --- PAINEL DO PROFESSOR ---
st.sidebar.write("---")
if st.sidebar.checkbox("🔒 Acesso do Professor"):
    senha = st.sidebar.text_input("Senha de Acesso:", type="password")
    if senha == "prof123":
        st.header("📊 Painel do Professor - Respostas do Laboratório")
        
        csv_file = "respostas_lab_virtual.csv"
        if os.path.exists(csv_file):
            df_prof = pd.read_csv(csv_file)
            st.dataframe(df_prof)
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                csv_data = df_prof.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Tabela CSV", csv_data, "respostas_lab.csv", "text/csv")
            with c_d2:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for root, dirs, files in os.walk("relatorios_lab"):
                        for file in files:
                            zf.write(os.path.join(root, file), file)
                zip_buffer.seek(0)
                st.download_button("📦 Baixar Todos os PDFs (ZIP)", zip_buffer, "relatorios_lab.zip", "application/zip")
        else:
            st.info("Nenhum envio registrado.")
    elif senha:
        st.sidebar.error("Senha incorreta.")
