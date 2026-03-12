import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- GENEL AYARLAR ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı (Ultra Stabil)")

# --- VERİTABANI BAĞLANTISI ---
@st.cache_resource
def get_db_conn():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def hafiza_oku(conn):
    try: return conn.read(ttl="30s")
    except: return pd.DataFrame(columns=["ilaclar", "rapor"])

# --- İLAÇ SÖZLÜĞÜ ---
def fda_verisi_cek(ilac_ismi):
    sozluk = {
        "dikloron": "diclofenac", "voltaren": "diclofenac", "dolorex": "diclofenac",
        "parol": "acetaminophen", "minoset": "acetaminophen",
        "coraspin": "aspirin", "ecopirin": "aspirin",
        "augmentin": "amoxicillin", "klamoks": "amoxicillin",
        "arveles": "dexketoprofen", "majezic": "flurbiprofen"
    }
    temiz = ilac_ismi.lower().strip().replace('ı','i').replace('ş','s').replace('ç','c')
    arama = sozluk.get(temiz, temiz).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac_ismi.upper()}: {d.get('indications_and_usage',[''])[0][:400]}"
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    user_api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if user_api_key: st.session_state["saved_key"] = user_api_key
    if st.button("Şifreyi Hatırla (Linke Göm)"):
        st.query_params["key"] = user_api_key
        st.success("Link güncellendi!")

# --- GİRİŞ ---
col1, col2 = st.columns(2)
with col1: i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
with col2: i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")

if st.button("Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("İlaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        conn = get_db_conn()
        df = hafiza_oku(conn) if conn else None
        
        found = False
        if df is not None and not df.empty:
            res = df[df['ilaclar'] == query_id]
            if not res.empty:
                st.success("✅ Hafızadan getirildi!")
                st.markdown(res.iloc[0]['rapor'])
                found = True

        if not found:
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("Sol menüden API anahtarınızı girin.")
            else:
                with st.spinner("Analiz ediliyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as ex:
                        results = list(ex.map(fda_verisi_cek, drugs))
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA verisi bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=active_key)
                            
                            # --- MODEL SEÇİCİ (404 HATASINI BİTİREN KISIM) ---
                            model_names = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro']
                            response = None
                            
                            for m_name in model_names:
                                try:
                                    model = genai.GenerativeModel(m_name)
                                    response = model.generate_content(f"Doktor için kısa Türkçe özet ve etkileşim raporu: {fda_metni}")
                                    if response: break
                                except Exception: continue # Eğer bu model 404 verirse bir sonrakini dene
                            
                            if response:
                                st.markdown(response.text)
                                if conn:
                                    try:
                                        new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [response.text]})
                                        conn.update(data=pd.concat([df, new_row], ignore_index=True))
                                    except: pass
                            else:
                                st.error("Google şu an hiçbir modeline izin vermiyor. Lütfen 5 dakika bekleyin.")
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
