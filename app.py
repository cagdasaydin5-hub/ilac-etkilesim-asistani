import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

# URL'den key'i güvenli bir şekilde çek
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("💊 Hekim İlaç Asistanı (Stabil Sürüm)")

# --- DARK MODE UYUMLU REHBER ---
with st.expander("❓ Sistem Neden Limit Hatası Veriyor?", expanded=True):
    st.warning("""
    **Limit Sorunu Yaşayanlar İçin:** Google Ücretsiz API'leri saniyede sadece 1-2 işleme izin verir. 
    Aynı anda çok fazla hekim sorgu yaparsa sistem "Limit 0" hatası verir. 
    **Çözüm:** 10 saniye bekleyip tekrar deneyin veya sol menüden yeni bir API anahtarı girin.
    """)

# --- GOOGLE SHEETS BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Veritabanı bağlantısı kurulamadı.")

def fda_verisi_cek(ilac_ismi):
    """FDA veritabanından veri çeker"""
    sozluk = {
        "parol": "acetaminophen", "dikloron": "diclofenac", 
        "coraspin": "aspirin", "verxant": "secukinumab",
        "augmentin": "amoxicillin", "arveles": "dexketoprofen"
    }
    temiz = ilac_ismi.lower().replace('ı','i').replace('ş','s')
    arama = sozluk.get(temiz, temiz).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=7)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"E: {d.get('indications_and_usage',[''])[0][:500]}\nD: {d.get('dosage_and_administration',[''])[0][:500]}"
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    user_api_key = st.text_input("Gemini API Anahtarınız", type="password", value=st.session_state.get("saved_key", ""))
    
    if user_api_key:
        st.session_state["saved_key"] = user_api_key

    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = user_api_key
        st.success("Link güncellendi! Bookmark yapabilirsiniz.")

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Coraspin")

# --- ANALİZ ---
if st.button("Güvenli Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen en az bir ilaç girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. HAFIZA KONTROLÜ
        try:
            df = conn.read(ttl="5s")
            existing = df[df['ilaclar'] == query_id]
            found = not existing.empty
        except: 
            found = False
            df = pd.DataFrame(columns=["ilaclar", "rapor"])
        
        if found:
            st.success("✅ Bu analiz kolektif hafızadan getirildi (Limit harcamaz)")
            st.markdown(existing.iloc[0]['rapor'])
        else:
            # 2. YENİ ANALİZ (1.5 FLASH)
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("❌ Bu kombinasyon hafızada yok. Devam etmek için API anahtarınızı girin.")
            else:
                with st.spinner("Analiz ediliyor..."):
                    fda_metni = ""
                    for d in drugs:
                        m = fda_verisi_cek(d)
                        if m: fda_metni += f"\n{d.upper()}: {m}\n"
                    
                    if not fda_metni:
                        st.error("İlaç FDA veritabanında bulunamadı.")
                    else:
                        try:
                            # 1.5 FLASH İÇİN EN DOĞRU MODEL İSMİ
                            genai.configure(api_key=active_key)
                            model = genai.GenerativeModel('gemini-1.5-flash-latest') 
                            
                            response = model.generate_content(
                                f"Doktor için özetle: {fda_metni}",
                                generation_config=genai.GenerationConfig(temperature=0.0)
                            )
                            rapor = response.text
                            st.markdown(rapor)
                            
                            # KAYDET
                            new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [rapor]})
                            df_updated = pd.concat([df, new_row], ignore_index=True)
                            conn.update(data=df_updated)
                            st.info("💡 Hafızaya eklendi!")
                        except Exception as e:
                            st.error(f"Google API Hatası: {str(e)}")
