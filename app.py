import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Klinik Karar Destek (Sade Format)")

# --- FDA VERİ ÇEKME ---
def fda_verisi_cek(ilac):
    sozluk = {
        "dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", 
        "coumadin": "warfarin", "augmentin": "amoxicillin", "klamoks": "amoxicillin",
        "beloc": "metoprolol", "lipitor": "atorvastatin", "glifor": "metformin"
    }
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=5'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = f"\n--- {ilac.upper()} ---"
            for d in res:
                metin += f"\nEndikasyon: {d.get('indications_and_usage',[''])[0][:300]}"
                metin += f"\nDozaj: {d.get('dosage_and_administration',[''])[0][:600]}"
                metin += f"\nEtkileşim: {d.get('drug_interactions',[''])[0][:500]}"
            return metin
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

# --- 4 İLAÇ GİRİŞİ ---
st.subheader("💊 İlaçları Girin (Maks 4)")
c1, c2, c3, c4 = st.columns(4)
with c1: i1 = st.text_input("1. İlaç")
with c2: i2 = st.text_input("2. İlaç")
with c3: i3 = st.text_input("3. İlaç")
with c4: i4 = st.text_input("4. İlaç")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = [d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()]
    
    if not drugs:
        st.warning("İlaç ismi girin.")
    else:
        active_key = st.session_state.get("saved_key")
        if not active_key:
            st.error("API Key gerekli.")
        else:
            with st.spinner("Analiz ediliyor..."):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    results = list(ex.map(fda_verisi_cek, drugs))
                
                fda_metni = "\n".join([r for r in results if r])
                
                if not fda_metni:
                    st.error("Veri bulunamadı.")
                else:
                    try:
                        genai.configure(api_key=active_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        # --- EN SADE VE TEMİZ PROMPT ---
                        prompt = f"""
                        Aşağıdaki ilaçları ({', '.join(drugs)}) analiz et ve sadece şu formatta yanıt ver:

                        ### ⚠️ KRİTİK ETKİLEŞİM UYARISI
                        (Bu ilaçlar arasında çapraz etkileşim varsa buraya madde madde yaz. Yoksa 'Klinik etkileşim saptanmadı' de.)

                        ### 📋 POZOLOJİ VE KLİNİK NOTLAR
                        | İlaç | Kullanım Amacı | Dozaj (Erişkin/Pediatri/Geriatri) | Gebelik | Kritik Uyarı |
                        | :--- | :--- | :--- | :--- | :--- |

                        KURALLAR:
                        - ASLA HTML KODU (<br>, <font> vb.) kullanma. 
                        - ASLA giriş/sonuç cümlesi yazma. 
                        - Sadece sistemik (Oral, IM, IV) formlara odaklan, topikalleri (jel vs.) pas geç.
                        - Pediatrik dozda FDA verisi yoksa genel tıp bilgini kullan.

                        FDA VERİLERİ:
                        {fda_metni}
                        """

                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Hata: {str(e)}")
