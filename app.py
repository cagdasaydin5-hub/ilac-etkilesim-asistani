import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
import concurrent.futures

# --- TEMEL AYARLAR ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı (Klasik Format)")

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    st.markdown("[Gemini API Key Al](https://aistudio.google.com/app/apikey)")
    key = st.text_input("API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    if st.button("Şifreyi Kaydet"):
        st.query_params["key"] = key
        st.success("Kaydedildi!")

# --- FDA VERİ ÇEKME ---
def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", "arveles": "dexketoprofen"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=5'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results'][0]
            return f"{ilac.upper()}:\nDozaj: {res.get('dosage_and_administration',[''])[0][:800]}\nEtkileşim: {res.get('drug_interactions',[''])[0][:600]}"
    except: return None
    return None

# --- GİRİŞ ---
c1, c2, c3, c4 = st.columns(4)
with c1: i1 = st.text_input("İlaç 1")
with c2: i2 = st.text_input("İlaç 2")
with c3: i3 = st.text_input("İlaç 3")
with c4: i4 = st.text_input("İlaç 4")

if st.button("Analizi Başlat", type="primary"):
    drugs = [d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()]
    if not drugs:
        st.warning("İlaç girin.")
    else:
        with st.spinner("Hazırlanıyor..."):
            with concurrent.futures.ThreadPoolExecutor() as ex:
                results = list(ex.map(fda_verisi_cek, drugs))
            
            fda_metni = "\n".join([r for r in results if r])
            
            try:
                genai.configure(api_key=st.session_state.get("saved_key", ""))
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # O SEVDİĞİN SADE VE GÜÇLÜ PROMPT
                prompt = f"""
                Sen bir tıp asistanısın. Aşağıdaki ilaçları ({', '.join(drugs)}) analiz et.
                
                1. KRİTİK ETKİLEŞİM: Bu ilaçlar arasında çapraz etkileşim varsa en başa büyük puntolarla yaz.
                2. TABLO: [İlaç], [Kullanım Amacı], [Pozoloji (Erişkin/Çocuk)], [Gebelik], [Kritik Uyarı] kolonlarından oluşan bir tablo yap.
                
                KURALLAR:
                - HTML kodları (<br> gibi) ASLA kullanma.
                - Sadece sistemik (oral/im/iv) formlara odaklan.
                - Türkiye klinik pratiğine (TİTCK) uygun yorumla.
                
                VERİLER:
                {fda_metni}
                """
                
                response = model.generate_content(prompt)
                # Manuel temizlik: AI ne basarsa bassın <br>'leri temizle
                st.markdown(response.text.replace("<br>", "\n").replace("<br/>", "\n"))
                
            except Exception as e:
                st.error(f"Hata: {str(e)}")
