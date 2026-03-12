import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı v6.5")
st.warning("⚠️ **KLİNİK UYARI:** Türkiye ruhsatları (KÜB/KT) önceliklidir. Bu veriler destek amaçlıdır.")

@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", "coumadin": "warfarin"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=10'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = ""
            for d in res:
                metin += f"\n--- {ilac.upper()} VERİSİ ---\n"
                metin += f"Doz: {d.get('dosage_and_administration',[''])[0][:600]}\n"
                metin += f"Etkileşim: {d.get('drug_interactions',[''])[0][:600]}\n"
                metin += f"Pediatrik: {d.get('pediatric_use',[''])[0][:400]}\n"
                metin += f"Gebelik: {d.get('pregnancy',[''])[0][:400]}\n"
            return metin
    except: return None
    return None

with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
    f1 = st.selectbox("Form (1)", ["Oral", "IM/IV", "Topikal"], key="f1")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Coumadin")
    f2 = st.selectbox("Form (2)", ["Oral", "IM/IV", "Topikal"], key="f2")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs_with_forms = []
    if i1: drugs_with_forms.append((i1, f1))
    if i2: drugs_with_forms.append((i2, f2))
    
    if not drugs_with_forms:
        st.warning("İlaç ismi girin.")
    else:
        query_id = " & ".join([f"{d}({f})" for d, f in drugs_with_forms])
        conn = get_db()
        found_rapor = None
        if conn:
            try:
                df = conn.read(ttl="5s")
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
                with st.spinner("İlaç etkileşimleri ve pediatrik dozlar taranıyor..."):
                    fda_metni = ""
                    secim_ozeti = ""
                    for d, f in drugs_with_forms:
                        m = fda_verisi_cek(d)
                        if m: 
                            fda_metni += m
                            secim_ozeti += f"- {d.upper()} ({f} formu) analiz edilecek.\n"
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bilgi bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            # --- KRİTİK PROMPT GÜNCELLEMESİ ---
                            prompt = f"""
                            Sen bir klinik asistanısın. Aşağıdaki verileri kullanarak NET BİR TABLO oluştur.

                            TABLO KOLONLARI:
                            | İlaç (Form) | Gebelik / Emzirme | Dozaj (Erişkin & Pediatri) | Önemli Etkileşimler | Kritik Uyarılar |

                            KESİN KURALLAR:
                            1. ETKİLEŞİM KOLONU: Seçilen ilaçların birbirleriyle veya genel (alkol, antikoagülan vb.) etkileşimlerini madde madde yaz.
                            2. PEDİATRİK VERİ: Eğer FDA metninde çocuk dozu yoksa, genel tıp bilgini kullan (Örn: "12 yaş altı kontrendike" veya "15 mg/kg"). "Veri yok" deme, klinik bir yönlendirme yap.
                            3. HTML YASAK: Asla <br> kullanma.
                            4. SEÇİLEN FORM: {secim_ozeti}

                            FDA VERİLERİ:
                            {fda_metni}
                            """

                            response = model.generate_content(prompt)
                            final_rapor = response.text
                            st.markdown(final_rapor)
                            
                            if conn:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [final_rapor]})
                                    conn.update(data=pd.concat([df, new_row], ignore_index=True))
                                except: pass
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
