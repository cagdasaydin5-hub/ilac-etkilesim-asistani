import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

# URL'den key'i otomatik çekme
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı (Final & Stabil)")

# --- HATA KORUMALI VERİTABANI BAĞLANTISI ---
@st.cache_resource
def get_db_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except:
        return None

def hafizayi_oku(conn):
    try:
        # ttl=60 ile her dakika bir kez veritabanına bakar, her sorguda değil. Bu hızı artırır.
        return conn.read(ttl="60s")
    except:
        return pd.DataFrame(columns=["ilaclar", "rapor"])

# --- TÜRKÇE İLAÇ SÖZLÜĞÜ (KRİTİK) ---
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
    user_api_key = st.text_input("Gemini API Anahtarı", type="password", value=st.session_state.get("saved_key", ""))
    if user_api_key: st.session_state["saved_key"] = user_api_key
    
    if st.button("Şifreyi Linke Göm (Hatırla)"):
        st.query_params["key"] = user_api_key
        st.success("Link güncellendi! Bookmark yapın.")

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Coraspin")

# --- ANALİZ MANTIĞI ---
if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. HAFIZA KONTROLÜ
        conn = get_db_connection()
        df = hafizayi_oku(conn) if conn else None
        
        found = False
        if df is not None and not df.empty:
            existing = df[df['ilaclar'] == query_id]
            if not existing.empty:
                st.success("✅ Kolektif hafızadan anında getirildi!")
                st.markdown(existing.iloc[0]['rapor'])
                found = True

        if not found:
            # 2. YENİ ANALİZ
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("Yeni analiz için lütfen API anahtarınızı girin.")
            else:
                with st.spinner("Analiz ediliyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        results = list(executor.map(fda_verisi_cek, drugs))
                    
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bu ilaçları bulamadım. Lütfen etken maddeyi deneyin.")
                    else:
                        try:
                            genai.configure(api_key=active_key)
                            # 404 Hatası almamak için en stabil modeli kullanıyoruz
                            model = genai.GenerativeModel('gemini-1.5-flash') 
                            
                            prompt = f"Doktor için çok kısa Türkçe özet ve etkileşim raporu: {fda_metni}"
                            response = model.generate_content(prompt)
                            rapor = response.text
                            
                            st.markdown(rapor)
                            
                            # 3. SESSİZ KAYIT (Hata verirse sistemi durdurmaz)
                            if conn:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [rapor]})
                                    df_updated = pd.concat([df, new_row], ignore_index=True)
                                    conn.update(data=df_updated)
                                except: pass 
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
