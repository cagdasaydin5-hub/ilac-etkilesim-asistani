import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı 2026", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı v3.1")

# --- VERİTABANI (HATA KORUMALI) ---
@st.cache_resource
def get_db_conn():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    user_api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    
    if user_api_key:
        st.session_state["saved_key"] = user_api_key
        # --- MODEL DEDEKTİFİ ---
        try:
            genai.configure(api_key=user_api_key)
            models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.success("✅ Bağlantı Başarılı!")
            st.write("Erişebildiğiniz Modeller:", models)
        except Exception as e:
            st.error("Anahtar hatalı veya liste alınamadı.")

    st.divider()
    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = user_api_key
        st.success("Link güncellendi!")

# --- İLAÇ ANALİZ FONKSİYONU ---
def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac.upper()}: {d.get('indications_and_usage',[''])[0][:500]}"
    except: return None
    return None

# --- GİRİŞ ---
i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")

if st.button("Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("İlaç ismi girin.")
    else:
        active_key = st.session_state.get("saved_key")
        if not active_key:
            st.error("Lütfen sol menüden API anahtarınızı girin.")
        else:
            with st.spinner("Analiz ediliyor..."):
                fda_metni = ""
                for d in drugs:
                    m = fda_verisi_cek(d)
                    if m: fda_metni += m + "\n"
                
                if not fda_metni:
                    st.error("FDA verisi bulunamadı.")
                else:
                    # --- ÇOKLU MODEL DENEME SİSTEMİ ---
                    model_listesi = ['gemini-3-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
                    basari = False
                    
                    for m_name in model_listesi:
                        try:
                            genai.configure(api_key=active_key)
                            model = genai.GenerativeModel(m_name)
                            response = model.generate_content(f"Doktor için kısa Türkçe özet: {fda_metni}")
                            st.markdown(response.text)
                            basari = True
                            break # Biri çalışırsa döngüden çık
                        except Exception as e:
                            if "404" in str(e): continue # Bu model yoksa sonrakini dene
                            else:
                                st.error(f"Hata ({m_name}): {str(e)}")
                                break
                    
                    if not basari:
                        st.error("Hiçbir model (3.0, 2.0, 1.5) yanıt vermedi. Lütfen anahtarın kotasını kontrol edin.")
