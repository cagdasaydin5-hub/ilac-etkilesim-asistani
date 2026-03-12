import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı 2026", page_icon="🛡️", layout="wide")

# URL'den key'i otomatik çekme (Bookmark desteği)
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı v3.0")

# --- DARK MODE UYUMLU REHBER ---
with st.expander("❓ Sistem Nasıl Çalışır?", expanded=False):
    st.info("""
    1. **Ücretsiz:** Daha önce analiz edilmiş ilaçlar hafızadan anında gelir (Kota harcamaz).
    2. **Yeni Analiz:** İlk kez sorgulanan ilaçlarda kendi API anahtarınızı kullanmanız gerekebilir.
    3. **Hız:** İlaçlar paralel sorgulanır, analiz Gemini 3 Flash ile saniyeler içinde biter.
    """)

# --- VERİTABANI BAĞLANTISI (HATA KORUMALI) ---
@st.cache_resource
def get_db_conn():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def hafiza_sorgula(drugs_id):
    try:
        conn = get_db_conn()
        if conn:
            df = conn.read(ttl="60s")
            res = df[df['ilaclar'] == drugs_id]
            if not res.empty: return res.iloc[0]['rapor']
    except: return None
    return None

# --- TÜRKÇE İLAÇ SÖZLÜĞÜ (FDA UYUMLU) ---
def fda_verisi_cek(ilac_ismi):
    sozluk = {
        "dikloron": "diclofenac", "voltaren": "diclofenac", "dolorex": "diclofenac",
        "parol": "acetaminophen", "minoset": "acetaminophen", "tamol": "acetaminophen",
        "coraspin": "aspirin", "ecopirin": "aspirin", "verxant": "secukinumab",
        "augmentin": "amoxicillin", "klamoks": "amoxicillin", "amoklavin": "amoxicillin",
        "arveles": "dexketoprofen", "majezic": "flurbiprofen", "apranax": "naproxen",
        "beloc": "metoprolol", "lipitor": "atorvastatin", "glifor": "metformin"
    }
    temiz = ilac_ismi.lower().strip().replace('ı','i').replace('ş','s').replace('ç','c')
    arama = sozluk.get(temiz, temiz).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac_ismi.upper()}: {d.get('indications_and_usage',[''])[0][:500]}"
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    user_api_key = st.text_input("Gemini API Anahtarınız", type="password", value=st.session_state.get("saved_key", ""))
    if user_api_key: st.session_state["saved_key"] = user_api_key
    
    if st.button("Şifreyi Hatırla (Linke Göm)"):
        st.query_params["key"] = user_api_key
        st.success("Link güncellendi! Bookmark yapın.")
    
    st.markdown("[🔑 Ücretsiz Anahtar Al](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("2026 Hekim Yardımlaşma Ağı")

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
    i3 = st.text_input("3. İlaç")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")
    i4 = st.text_input("4. İlaç")

# --- ANALİZ MANTIĞI ---
if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen en az bir ilaç girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. HAFIZA KONTROLÜ (KOTA HARCAMAZ)
        rapor = hafiza_sorgula(query_id)
        
        if rapor:
            st.success("✅ Kolektif hafızadan getirildi (Hızlı & Ücretsiz)")
            st.markdown(rapor)
        else:
            # 2. YENİ ANALİZ
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("Bu kombinasyon hafızada yok. Yeni analiz için lütfen sol menüden API anahtarınızı girin.")
            else:
                with st.spinner("FDA taranıyor ve Gemini 3 Flash analiz ediyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        results = list(executor.map(fda_verisi_cek, drugs))
                    
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bu ilaçları bulamadım.")
                    else:
                        try:
                            genai.configure(api_key=active_key)
                            # 2026 GÜNCELLEMESİ: Gemini 3 Flash
                            model = genai.GenerativeModel('gemini-3-flash') 
                            
                            prompt = f"Sen bir farmakologsun. Şu FDA verilerini doktor için kısa Türkçe özetle ve etkileşim uyarısı yap: {fda_metni}"
                            response = model.generate_content(prompt)
                            
                            final_rapor = response.text
                            st.markdown(final_rapor)
                            
                            # 3. SESSİZ KAYIT
                            try:
                                conn = get_db_conn()
                                if conn:
                                    df_old = conn.read()
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [final_rapor]})
                                    conn.update(data=pd.concat([df_old, new_row], ignore_index=True))
                            except: pass # Kayıt hatası analizi bozmasın
                            
                        except Exception as e:
                            st.error(f"Kota veya Bağlantı Hatası: {str(e)}")
