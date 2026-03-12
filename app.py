import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı v8.5", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Klinik Karar Destek: Sistemik Formlar & Etkileşim")
st.error("⚠️ **DİKKAT:** Yapay zeka özetidir. Doz ve etkileşim kontrolü hekim sorumluluğundadır.")

# --- VERİTABANI BAĞLANTISI ---
@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac):
    sozluk = {
        "dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", 
        "coumadin": "warfarin", "augmentin": "amoxicillin", "klamoks": "amoxicillin",
        "beloc": "metoprolol", "lipitor": "atorvastatin", "glifor": "metformin", "arveles": "dexketoprofen"
    }
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    # Formları yakalamak için derin tarama (limit=10)
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=10'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = f"\n--- {ilac.upper()} ANALİZ VERİSİ ---\n"
            for d in res:
                # Sadece sistemik yolları içeren kayıtları yakalamaya çalışıyoruz
                metin += f"Endikasyon: {d.get('indications_and_usage',[''])[0][:300]}\n"
                metin += f"Dozaj ve Uygulama: {d.get('dosage_and_administration',[''])[0][:800]}\n"
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
st.subheader("💊 İlaç Listesi (Maks 4 - Sadece Sistemik)")
c1, c2, c3, c4 = st.columns(4)
with c1: i1 = st.text_input("1. İlaç", key="i1")
with c2: i2 = st.text_input("2. İlaç", key="i2")
with c3: i3 = st.text_input("3. İlaç", key="i3")
with c4: i4 = st.text_input("4. İlaç", key="i4")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = [d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()]
    
    if not drugs:
        st.warning("En az bir ilaç ismi girin.")
    else:
        active_key = st.session_state.get("saved_key")
        if not active_key:
            st.error("Lütfen API Key girin.")
        else:
            with st.spinner("Topikaller eleniyor, sistemik formlar analiz ediliyor..."):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    results = list(ex.map(fda_verisi_cek, drugs))
                
                fda_metni = "\n".join([r for r in results if r])
                
                if not fda_metni:
                    st.error("Veri bulunamadı.")
                else:
                    try:
                        genai.configure(api_key=active_key)
                        # Senin listende çalışan en güncel model
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt = f"""
                        Sen aile hekimine yardım etmek üzere uzman bir klinik farmakoloji asistanısın. Aşağıdaki verileri analiz et ve bir tablo oluştur.

                        ÖNEMLİ KRİTERLER:
                        1. TOPİKAL FORMLARI YOK SAY: Jel, krem, merhem gibi topikal formları analizden tamamen çıkar. 
                        2. SADECE SİSTEMİK FORMLARA ODAKLAN: Oral, IM ve IV formların pozolojilerini getir.
                        3. ETKİLEŞİM ANALİZİ: Girilen şu ilaçlar ({', '.join(drugs)}) arasındaki çapraz etkileşimleri EN BAŞA, kırmızı/kalın uyarı şeklinde yaz.
                        4. TABLO KOLONLARI: [İlaç / Etken Madde], [Kullanım Amacı], [Pozoloji (Oral/IM/IV)], [Pediatrik/Geriatrik Doz], [Gebelik & Kritik Uyarı].

                        KESİN KURALLAR:
                        - "Sayın Doktor" gibi ifadeler ASLA olmayacak.
                        - HTML (<br>) kullanma.
                        - Bilgi yoksa uydurma.
                        
                        FDA VERİLERİ:
                        {fda_metni}
                        """

                        response = model.generate_content(prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Hata: {str(e)}")
