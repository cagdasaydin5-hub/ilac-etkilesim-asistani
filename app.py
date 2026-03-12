import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊")

# URL'den key çekme
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("💊 Hekim İlaç Asistanı")

# --- HAFIZA (SADECE OKUMA) ---
@st.cache_resource
def get_conn():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def hafiza_kontrol(drug_names):
    conn = get_conn()
    if conn:
        try:
            df = conn.read(ttl="10m")
            res = df[df['ilaclar'] == drug_names]
            if not res.empty: return res.iloc[0]['rapor']
        except: return None
    return None

# --- FDA SORGUSU ---
def fda_sorgula(isim):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin"}
    arama = sozluk.get(isim.lower().strip(), isim).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{isim.upper()}:\n{d.get('indications_and_usage',[''])[0][:500]}"
    except: return None
    return None

# --- GİRİŞ VE ANALİZ ---
with st.sidebar:
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

i1 = st.text_input("1. İlaç")
i2 = st.text_input("2. İlaç")

if st.button("Analiz Et", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("İlaç ismi girin.")
    else:
        query = ", ".join(drugs)
        
        # Önce hafızaya bak
        rapor = hafiza_kontrol(query)
        
        if rapor:
            st.success("✅ Hafızadan getirildi")
            st.markdown(rapor)
        else:
            if not st.session_state.get("saved_key"):
                st.error("Lütfen API Key girin.")
            else:
                with st.spinner("Analiz ediliyor..."):
                    fda_metni = ""
                    for d in drugs:
                        m = fda_sorgula(d)
                        if m: fda_metni += m + "\n"
                    
                    if not fda_metni:
                        st.error("Veri bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            # EN STABİL MODEL İSMİ
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            response = model.generate_content(f"Doktor için kısa özetle: {fda_metni}")
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"Google Hatası: {str(e)}")
