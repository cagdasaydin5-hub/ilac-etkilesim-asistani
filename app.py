import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Klinik Karar Destek: Etkileşim & Pozoloji")
st.error("⚠️ **DİKKAT:** Bu analiz bir yapay zeka özetidir. İlaç etkileşimleri ve dozajlar için nihai kontrol hekim sorumluluğundadır.")

@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=get_db) # Cache için isim değişikliği gerekebilir
    except: return None

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
            metin = f"\n--- {ilac.upper()} ANALİZ VERİSİ ---\n"
            for d in res:
                metin += f"Endikasyon: {d.get('indications_and_usage',[''])[0][:300]}\n"
                metin += f"Dozaj: {d.get('dosage_and_administration',[''])[0][:500]}\n"
                metin += f"Etkileşimler: {d.get('drug_interactions',[''])[0][:500]}\n"
            return metin
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

# --- 4 İLAÇ GİRİŞİ ---
st.subheader("💊 İlaç Listesi (Maks 4)")
c1, c2, c3, c4 = st.columns(4)
with c1: i1 = st.text_input("1. İlaç")
with c2: i2 = st.text_input("2. İlaç")
with c3: i3 = st.text_input("3. İlaç")
with c4: i4 = st.text_input("4. İlaç")

if st.button("Klinik Etkileşim Analizini Başlat", type="primary"):
    drugs = [d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()]
    
    if not drugs:
        st.warning("En az bir ilaç girin.")
    else:
        active_key = st.session_state.get("saved_key")
        if not active_key:
            st.error("API Key gerekli.")
        else:
            with st.spinner("İlaçlar arası etkileşimler ve pozolojiler hesaplanıyor..."):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    results = list(ex.map(fda_verisi_cek, drugs))
                
                fda_metni = "\n".join([r for r in results if r])
                
                if not fda_metni:
                    st.error("Veri bulunamadı.")
                else:
                    try:
                        genai.configure(api_key=active_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt = f"""
                        Sen bir klinik farmakoloji asistanısın. Aşağıdaki verileri analiz et ve bir Aile Hekimi için şu formatta bir rapor oluştur:

                        1. ⚠️ KRİTİK ETKİLEŞİM UYARISI: Yazılan ilaçların ({', '.join(drugs)}) kendi aralarındaki etkileşimlerini EN BAŞA, kalın harflerle yaz. Risk yüksekse belirt.
                        
                        2. POZOLOJİ TABLOSU:
                        | İlaç / Etken Madde | Ne İçin Kullanılır? | Pediatrik Doz | Yetişkin Doz | Geriatrik Doz |
                        
                        3. GEBELİK / EMZİRME: Her ilaç için risk kategorisini belirt.

                        KESİN KURALLAR:
                        - "Sayın Doktor" gibi gereksiz hitaplar ASLA olmayacak.
                        - Pediatrik ve Geriatrik dozlarda spesifik kısıtlamaları (Örn: Reye sendromu, Renal doz ayarı) mutlaka belirt.
                        - HTML (<br>) kullanma.
                        
                        FDA VERİLERİ:
                        {fda_metni}
                        """

                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Hata: {str(e)}")
