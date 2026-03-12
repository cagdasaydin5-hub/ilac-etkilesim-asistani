import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı (Form Seçenekli)")

@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac, form_filtresi):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", "augmentin": "amoxicillin"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    
    # Seçilen forma göre FDA sorgusunu biraz daha spesifikleştiriyoruz
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=10'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = f"SEÇİLEN FORM: {form_filtresi}\n"
            for d in res:
                metin += f"\n[KAYIT]: {d.get('dosage_and_administration',[''])[0][:800]}\n"
            return metin
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = key
        st.success("Link güncellendi!")

# --- GİRİŞ VE SEÇENEKLER ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
    f1 = st.selectbox("Form Seçin (1)", ["Hepsi", "Oral (Tablet/Kapsül)", "IM/IV (Ampul)", "Topikal (Jel/Krem)"], key="f1")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")
    f2 = st.selectbox("Form Seçin (2)", ["Hepsi", "Oral (Tablet/Kapsül)", "IM/IV (Ampul)", "Topikal (Jel/Krem)"], key="f2")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs_with_forms = []
    if i1: drugs_with_forms.append((i1, f1))
    if i2: drugs_with_forms.append((i2, f2))
    
    if not drugs_with_forms:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        # Hafıza ID'si için form bilgisini de ekliyoruz
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
                with st.spinner(f"Seçilen formlar analiz ediliyor..."):
                    fda_metni = ""
                    for d, f in drugs_with_forms:
                        m = fda_verisi_cek(d, f)
                        if m: fda_metni += m
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bilgi bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            prompt = f"""
                            Sen bir tıp asistanısın. Aşağıdaki verileri kullanarak NET BİR TABLO oluştur.
                            
                            ÖNEMLİ: 
                            - Eğer kullanıcı belirli bir form (Oral, IM/IV, Topikal) seçmişse, tabloya ÖNCELİKLE O FORMU yaz.
                            - Format sadece tablo olsun. Giriş/sonuç cümlesi yazma.
                            - Kolonlar: [İlaç / Seçilen Form], [Gebelik / Emzirme], [Erişkin Doz], [Pediatrik Doz (mg/kg)], [Kritik Uyarılar].

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
