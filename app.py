import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Klinik Karar Destek (TİTCK Standartlı)")

def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", "arveles": "dexketoprofen"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=5'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = f"\n--- {ilac.upper()} ---\n"
            for d in res:
                metin += f"Dozaj: {d.get('dosage_and_administration',[''])[0][:600]}\n"
                metin += f"Etkileşim: {d.get('drug_interactions',[''])[0][:500]}\n"
            return metin
    except: return None
    return None

with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

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
            with st.spinner("TİTCK standartlarına göre analiz ediliyor..."):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    results = list(ex.map(fda_verisi_cek, drugs))
                
                fda_metni = "\n".join([r for r in results if r])
                
                try:
                    genai.configure(api_key=active_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # --- TİTCK ODAKLI PROMPT ---
                    prompt = f"""
                    Sen Türkiye'de çalışan bir klinik farmakologsun. Aşağıdaki FDA verilerini al ve 
                    Türkiye TİTCK (KÜB/KT) standartlarına ve yerel klinik pratiğimize göre yorumla.

                    ### ⚠️ KRİTİK ETKİLEŞİM UYARISI
                    - {', '.join(drugs)} ilaçlarının Türkiye'deki klinik kullanımda bilinen etkileşimleri.

                    ### 📋 TİTCK STANDARTLI POZOLOJİ TABLOSU
                    | İlaç | Endikasyon (TR) | Dozaj (Oral/IM/IV) | Çocuk/Yaşlı Dozu | Gebelik |
                    | :--- | :--- | :--- | :--- | :--- |

                    KESİN KURALLAR:
                    1. HTML ve gereksiz hitap kullanma.
                    2. FDA verisinde "topikal" görsen bile Türkiye'de sık kullanılan "Sistemik" formları ön plana çıkar.
                    3. Gebelik kategorisinde TİTCK rehberini baz al.
                    
                    VERİLER:
                    {fda_metni}
                    """

                    response = model.generate_content(prompt)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Hata: {str(e)}")
