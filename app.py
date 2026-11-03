import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw
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

st.set_page_config(page_title="RPG Laboratório: Padronização de AgNO3", layout="wide")

st.title("🧪 RPG Analítico: Preparo e Padronização de $\text{AgNO}_3$")
st.write("Avance pelas fases do laboratório tomando decisões analíticas corretas, pesando na balança e titulando a solução.")

# --- INICIALIZAÇÃO SEGURA DO SESSION STATE (EVITA NameError) ---
if 'fase' not in st.session_state:
    st.session_state.fase = 1
if 'massa_pesada' not in st.session_state:
    st.session_state.massa_pesada = 0.0
if 'v_titulante_add' not in st.session_state:
    st.session_state.v_titulante_add = 0.0

# --- FUNÇÕES AUXILIARES GLOBAIS ---
def desenhar_balanca(massa):
    img = Image.new("RGBA", (320, 220), (240, 240, 245, 255))
    draw = ImageDraw.Draw(img)
    # Corpinho da Balança
    draw.rectangle([20, 80, 300, 200], fill=(200, 205, 210), outline=(50, 50, 50), width=3)
    # Prato da Balança
    draw.ellipse([90, 65, 230, 85], fill=(150, 150, 160), outline=(0, 0, 0), width=2)
    # Display LCD Digital
    draw.rectangle([80, 130, 240, 180], fill=(10, 40, 10), outline=(0, 0, 0), width=2)
    draw.text((95, 145), f"{massa:.4f} g", fill=(50, 255, 50))
    # Vidro de Relógio + Sal Branco
    if massa > 0:
        draw.ellipse([110, 58, 210, 72], fill=(220, 220, 230, 180), outline=(100, 100, 100))
        draw.ellipse([140, 60, 180, 68], fill=(255, 255, 255))
    return img

def desenhar_mohr(v_tit, cor_rgb):
    img = Image.new("RGBA", (300, 350), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # Bureta
    draw.rectangle([135, 20, 165, 180], outline="black", width=2)
    alt_liq = min(178, 30 + int(v_tit * 6))
    draw.rectangle([137, alt_liq, 163, 178], fill=(200, 220, 240, 200))
    draw.rectangle([130, 180, 170, 188], fill="gray")
    # Erlenmeyer com o viragem de cor
    erlen = [(150, 230), (110, 260), (70, 320), (230, 320), (190, 260)]
    draw.polygon([(160, 280), (230, 280), (230, 320), (70, 320), (70, 280)], fill=cor_rgb)
    draw.polygon(erlen, outline="black", width=2)
    return img

def gerar_pdf_jogo(nome, mat, m_pesada, v_viragem, conc_calc, file_script):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>Certificado de Conclusão - RPG Laboratório de Química Analítica</b>", styles['Title']))
    elements.append(Spacer(1, 10))
    info = f"<b>Aluno:</b> {nome}<br/><b>Matrícula:</b> {mat}<br/><b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(info, styles['Normal']))
    elements.append(Spacer(1, 12))

    resumo = f"""
    <b>Massa Pesada na Balança:</b> {m_pesada} g<br/>
    <b>Método Escolhido:</b> Argentimetria / Método de Mohr (NaCl + K<sub>2</sub>CrO<sub>4</sub>)<br/>
    <b>Volume no Ponto de Equivalência:</b> {v_viragem} mL<br/>
    <b>Concentração Real Determinada:</b> {conc_calc} mol/L
    """
    elements.append(Paragraph(resumo, styles['Normal']))
    elements.append(Spacer(1, 12))

    img_m = Image.open(file_script).convert("RGB")
    img_m.thumbnail((400, 400))
    temp_p = f"temp_rpg_{mat}.jpg"
    img_m.save(temp_p)
    elements.append(RLImage(temp_p, width=320, height=320))

    doc.build(elements)
    if os.path.exists(temp_p):
        os.remove(temp_p)
    buffer.seek(0)
    return buffer.getvalue()

# --- 1. IDENTIFICAÇÃO DO ESTUDANTE ---
st.sidebar.header("Identificação do Aluno")
nome_aluno = st.sidebar.text_input("Nome Completo:")
matricula_input = st.sidebar.text_input("Matrícula (apenas números):")

if not nome_aluno or not matricula_input or not matricula_input.isdigit():
    st.warning("⚠️ Digite seu nome e matrícula na barra lateral para iniciar o jogo de laboratório.")
    st.stop()

matricula = int(matricula_input)
ultimos_2 = matricula % 100

# Parâmetros Químicos Globais (Evita NameError)
MM_AgNO3 = 169.87
MM_NaCl = 58.44
vol_solucao_preparar = 250.0 
conc_alvo_agno3 = round(0.010 + (ultimos_2 * 0.0005), 4) 
massa_agno3_teorica = round(conc_alvo_agno3 * (vol_solucao_preparar / 1000.0) * MM_AgNO3, 4)
v_equiv_padronizacao = round((10.0 * 0.010) / conc_alvo_agno3, 2)

# --- FASE 1: O DESAFIO DO DIA ---
if st.session_state.fase == 1:
    st.header("📋 FASE 1: A Missão Analítica")
    st.info(rf"""
    **Desafio de Laboratório:**
    Você precisa preparar exatamente **{vol_solucao_preparar} mL** de uma solução de Nitrato de Prata ($\text{{AgNO}}_3$) com concentração aproximada de **{conc_alvo_agno3} mol/L**.
    
    *Massa Molar do $\text{{AgNO}}_3$ = {MM_AgNO3} g/mol*
    """)
    
    massa_calc = st.number_input("Digite a massa (em gramas) que você deve pesar na balança analítica:", format="%.4f")
    
    if st.button("Ir para a Bancada de Pesagem ➡️"):
        if abs(massa_calc - massa_agno3_teorica) < 0.005:
            st.success("✨ Cálculo de massa exato! Indo para a balança analítica...")
            st.session_state.fase = 2
            st.rerun()
        else:
            st.error(f"❌ Cálculo incorreto. Revise a conta: $m = C \cdot V \cdot MM$. (Valor esperado em torno de {massa_agno3_teorica} g).")

# --- FASE 2: BANCADA DE PESAGEM ---
elif st.session_state.fase == 2:
    st.header("⚖️ FASE 2: Balança Analítica Digital")
    st.write(f"Adicione $\text{AgNO}_3$ ao vidro de relógio até atingir a massa calculada ({massa_agno3_teorica} g).")
    
    c_bal1, c_bal2 = st.columns([1, 1])
    
    with c_bal1:
        st.subheader("Operação da Espátula")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if st.button("➕ 0.100 g"):
                st.session_state.massa_pesada = round(st.session_state.massa_pesada + 0.100, 4)
        with col_m2:
            if st.button("➕ 0.010 g"):
                st.session_state.massa_pesada = round(st.session_state.massa_pesada + 0.010, 4)
        with col_m3:
            if st.button("➕ 0.001 g"):
                st.session_state.massa_pesada = round(st.session_state.massa_pesada + 0.001, 4)
                
        if st.button("🧹 Tarar / Zerar Balança"):
            st.session_state.massa_pesada = 0.0

    with c_bal2:
        st.image(desenhar_balanca(st.session_state.massa_pesada), caption="Balança Analítica com Vidro de Relógio")
        
    if st.button("Dissolver, Aferir Balão de 250 mL e Avançar ➡️"):
        if abs(st.session_state.massa_pesada - massa_agno3_teorica) < 0.002:
            st.success("Massa pesada com precisão analítica! Solução preparada no balão volumétrico.")
            st.session_state.fase = 3
            st.rerun()
        else:
            st.error("A massa pesada na balança está muito distante do valor correto. Ajuste com a espátula!")

# --- FASE 3: DECISÃO ANALÍTICA ---
elif st.session_state.fase == 3:
    st.header("🧠 FASE 3: Tomada de Decisão Analítica")
    st.write("Responda às questões técnicas sobre o comportamento do reagente para prosseguir:")
    
    q1 = st.radio("1. O Nitrato de Prata (AgNO₃) pode ser considerado um Padrão Primário?", 
                  ["Selecione...", "Sim, possui massa molar elevada e alta pureza sem necessidade de padronização.",
                   "Não, é higroscópico, fotossensível e sua concentração real deve ser determinada por padronização."])
                   
    q2 = st.selectbox("2. Qual Padrão Primário deve ser utilizado para padronizar o $\text{AgNO}_3$?",
                      ["Selecione...", "Biftalato de Potássio (KHP)", "Cloreto de Sódio (NaCl) previamente seco", "Carbonato de Sódio (Na2CO3)"])
                      
    q3 = st.selectbox("3. Qual o Indicador correto para a Titulação de Precipitação pelo Método de Mohr?",
                      ["Selecione...", "Fenolftaleína", "Alaranjado de Metila", "Cromato de Potássio (K2CrO4)"])
                      
    if st.button("Validar Decisões Teóricas ➡️"):
        if q1.startswith("Não") and "NaCl" in q2 and "K2CrO4" in q3:
            st.success("🎯 Respostas perfeitas! O Método de Mohr utiliza NaCl como padrão e K2CrO4 como indicador.")
            st.session_state.fase = 4
            st.rerun()
        else:
            st.error("❌ Uma ou mais escolhas teóricas estão incorretas. Lembre-se: argentimetria direta exige NaCl e Cromato de Potássio!")

# --- FASE 4: TITULAÇÃO ---
elif st.session_state.fase == 4:
    st.header("🔬 FASE 4: Titulação Argentimétrica (Método de Mohr)")
    st.write("Titule uma alíquota de **10.0 mL de NaCl 0.010 mol/L** + indicador Cromato de Potássio adicionando solução de Nitrato de Prata da bureta:")
    
    col_t1, col_t2 = st.columns([1, 1])
    
    with col_t1:
        st.subheader("Controle da Bureta ($\text{AgNO}_3$)")
        c_b1, c_b2, c_b3 = st.columns(3)
        with c_b1:
            if st.button("➕ 1.0 mL"):
                st.session_state.v_titulante_add = round(st.session_state.v_titulante_add + 1.0, 2)
        with c_b2:
            if st.button("➕ 0.1 mL"):
                st.session_state.v_titulante_add = round(st.session_state.v_titulante_add + 0.1, 2)
        with c_b3:
            if st.button("🔄 Zerar Bureta"):
                st.session_state.v_titulante_add = 0.0
                
        v_add = st.session_state.v_titulante_add
        st.write(f"Volume adicionado: **{v_add:.2f} mL**")
        
        delta = v_add - v_equiv_padronizacao
        if delta < -0.2:
            cor_sol = (240, 230, 80, 230)
            estado = "🟡 Solução Amarela (Precipitado branco de AgCl formando)"
        elif -0.2 <= delta <= 0.2:
            cor_sol = (210, 100, 50, 240)
            estado = "🧱 VIRAGEM! Precipitado Vermelho-Tijolo de Ag2CrO4 detectado!"
        else:
            cor_sol = (170, 30, 20, 255)
            estado = "🔴 Excesso de Titulante (Supertitulado)"
            
        st.info(f"**Aspecto Visual:** {estado}")

    with col_t2:
        st.image(desenhar_mohr(st.session_state.v_titulante_add, cor_sol), caption="Viragem do Método de Mohr")
        
    if st.button("Registrar Volume de Viragem e Ir para Cálculos ➡️"):
        if st.session_state.v_titulante_add > 0:
            st.session_state.fase = 5
            st.rerun()
        else:
            st.error("Adicione titulante da bureta para observar a viragem antes de prosseguir.")

# --- FASE 5: REAÇÃO QUÍMICA E CÁLCULOS ---
elif st.session_state.fase == 5:
    st.header("📝 FASE 5: Equação Química e Resolução Manuscrita")
    
    st.write(f"Volume do ponto de equivalência lido: **{st.session_state.v_titulante_add} mL de $\text{AgNO}_3$**.")
    st.write("Escreva no papel:")
    st.markdown("1. A **equação química balanceada** da reação de padronização entre $\text{AgNO}_3$ e $\text{NaCl}$.\n2. A **equação da reação indicadora** ($\text{Ag}_2\text{CrO}_4$).\n3. O cálculo da **concentração real exata** da solução de $\text{AgNO}_3$.")
    
    file_manuscrito = st.file_uploader("Upload da foto do manuscrito:", type=["jpg", "jpeg", "png", "heic"])
    
    if file_manuscrito:
        st.image(Image.open(file_manuscrito), caption="Resolução Manuscrita", width=350)
        
        st.subheader("Transcrição dos Resultados Finais")
        c1, c2 = st.columns(2)
        with c1:
            conc_real_aluno = st.number_input("Concentração Real Calculada de AgNO3 (mol/L):", format="%.5f")
        with c2:
            eq_aluno = st.text_input("Escreva a Equação Química Global (ex: AgNO3 + NaCl -> ...):")

        if st.button("🏆 Finalizar Missão e Enviar Atividade"):
            pdf_bytes = gerar_pdf_jogo(nome_aluno, matricula, st.session_state.massa_pesada, st.session_state.v_titulante_add, conc_real_aluno, file_manuscrito)
            
            os.makedirs("relatorios_rpg", exist_ok=True)
            pdf_path = f"relatorios_rpg/{nome_aluno.replace(' ', '_')}_{matricula}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            registro = {
                "Nome": nome_aluno.strip().title(),
                "Matricula": matricula,
                "DataEnvio": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Massa_Pesada": st.session_state.massa_pesada,
                "V_Viragem": st.session_state.v_titulante_add,
                "Conc_Real_Aluno": conc_real_aluno,
                "PDF": pdf_path
            }

            csv_file = "respostas_rpg_quimica.csv"
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
            else:
                df = pd.DataFrame([registro])

            df.sort_values(by="Nome", ascending=True).to_csv(csv_file, index=False)
            st.success("🎉 Parabéns! Você concluiu a missão do laboratório com sucesso! O relatório PDF foi gerado.")

# --- PAINEL DO PROFESSOR ---
st.sidebar.write("---")
if st.sidebar.checkbox("🔒 Acesso do Professor"):
    senha = st.sidebar.text_input("Senha de Acesso:", type="password")
    if senha == "prof123":
        st.header("📊 Painel do Professor - Respostas RPG")
        csv_file = "respostas_rpg_quimica.csv"
        if os.path.exists(csv_file):
            df_prof = pd.read_csv(csv_file)
            st.dataframe(df_prof)
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.download_button("📥 Baixar Tabela CSV", df_prof.to_csv(index=False).encode('utf-8'), "respostas_rpg.csv", "text/csv")
            with c_d2:
                zip_b = io.BytesIO()
                with zipfile.ZipFile(zip_b, "w") as zf:
                    for root, dirs, files in os.walk("relatorios_rpg"):
                        for file in files:
                            zf.write(os.path.join(root, file), file)
                zip_b.seek(0)
                st.download_button("📦 Baixar Relatórios em ZIP", zip_b, "relatorios_rpg.zip", "application/zip")
