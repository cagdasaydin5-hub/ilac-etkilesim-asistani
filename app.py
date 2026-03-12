import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı (Nokta Atışı)")

@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    # Tüm formları yakalamak için limit=10 devam ediyor, filtrelemeyi AI yapacak
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=10'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = ""
            for d in res:
                metin += f"\n[VERİ]: {d.get('dosage_and_administration',[''])[0][:800]}\n"
            return metin
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key

# --- GİRİŞ VE SEÇENEKLER ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
    f1 = st.selectbox("Form Seçin (1)", ["Oral", "IM/IV", "Topikal"], key="f1")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")
    f2 = st.selectbox("Form Seçin (2)", ["Oral", "IM/IV", "Topikal"], key="f2")

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
                with st.spinner(f"Sadece seçilen formlar süzülüyor..."):
                    fda_metni = ""
                    secim_ozeti = ""
                    for d, f in drugs_with_forms:
                        m = fda_verisi_cek(d)
                        if m: fda_metni += f"\n--- {d.upper()} İÇİN VERİ SETİ ---\n" + m
                        secim_ozeti += f"{d.upper()} için SADECE {f} formunu analiz et.\n"
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bilgi bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            # --- SERT FİLTRELEME PROMPTU ---
                            prompt = f"""
                            Sen bir klinik asistanısın. Aşağıdaki verilerden SADECE istenen formları ayıkla ve tablo yap.
                            
                            KULLANICI SEÇİMİ:
                            {secim_ozeti}

                            KESİN KURALLAR:
                            1. Tabloda seçilen form dışında (örn. kullanıcı IM seçtiyse Oral veya Jel) HİÇBİR satır veya bilgi olmayacak.
                            2. Tablo kolonları: [İlaç], [Seçilen Form], [Gebelik/Emzirme], [Erişkin Doz], [Pediatrik Doz (mg/kg)], [Kritik Uyarılar].
                            3. Giriş/Sonuç cümlesi yazma. Sadece tabloyu ver.
                            4. Seçilen form veride yoksa "Bu form için spesifik veri bulunamadı" yaz.

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
