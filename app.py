import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı 2026", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı v4.1")

@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "voltaren": "diclofenac", "parol": "acetaminophen", "arveles": "dexketoprofen"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    # limit=3 yaparak farklı formların (tablet, ampul, jel) kayıtlarına ulaşıyoruz
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=3'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = ""
            for d in res:
                metin += f"\n--- {ilac.upper()} Form Verisi ---\n"
                metin += f"Endikasyon: {d.get('indications_and_usage',[''])[0][:300]}\n"
                metin += f"Dozaj: {d.get('dosage_and_administration',[''])[0][:300]}\n"
            return metin
    except: return None
    return None

with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = key
        st.success("Link güncellendi!")

i1 = st.text_input("1. İlaç")
i2 = st.text_input("2. İlaç")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        conn = get_db()
        found_rapor = None
        if conn:
            try:
                df = conn.read(ttl="10s")
                res = df[df['ilaclar'] == query_id]
                if not res.empty: found_rapor = res.iloc[0]['rapor']
            except: pass

        if found_rapor:
            st.success("✅ Hafızadan getirildi")
            st.markdown(found_rapor)
        else:
            if not st.session_state.get("saved_key"):
                st.error("API Key gerekli.")
            else:
                with st.spinner("Tüm formlar (Oral, IM, Topikal) analiz ediliyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as ex:
                        results = list(ex.map(fda_verisi_cek, drugs))
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA verisi bulunamadı.")
                    else:
                        # PROMPT GÜNCELLEMESİ: YAPAY ZEKAYA TÜM FORMLARI YAZDIRIYORUZ
                        model_siralamasi = ['gemini-2.5-flash', 'gemini-1.5-flash-latest']
                        final_response = None
                        genai.configure(api_key=st.session_state["saved_key"])
                        
                        prompt = f"""
                        Sen uzman bir farmakologsun. Aşağıdaki FDA verilerini kullanarak doktor için Türkçe rapor hazırla:
                        {fda_metni}

                        ÖNEMLİ TALİMATLAR:
                        1. Eğer ilacın Oral (Tablet/Kapsül), Parenteral (IM/IV Ampul) ve Topikal (Jel/Krem) formları varsa, HER BİRİ İÇİN AYRI dozaj bilgisi ver.
                        2. Klinik pratik için en kritik dozları ve etkileşimleri vurgula.
                        3. Gebelik riskini (A, B, C, D, X) mutlaka belirt.
                        """

                        for m_name in model_siralamasi:
                            try:
                                model = genai.GenerativeModel(m_name)
                                response = model.generate_content(prompt)
                                final_response = response.text
                                break
                            except: continue
                        
                        if final_response:
                            st.markdown(final_response)
                            if conn:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [final_response]})
                                    conn.update(data=pd.concat([df, new_row], ignore_index=True))
                                except: pass
                        else:
                            st.error("Şu an modeller yoğun, lütfen tekrar deneyin.")
