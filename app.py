import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hızlı Hekim Asistanı", page_icon="⚡", layout="wide")

# URL'den key'i otomatik çekme
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("⚡ Hızlı Hekim Asistanı")

# --- GOOGLE SHEETS BAĞLANTISI (HATA KORUMALI) ---
def hafizayi_getir():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # ttl="10s" ile her 10 saniyede bir tabloyu yeniler
        return conn, conn.read(ttl="10s")
    except Exception:
        return None, None

def fda_verisi_cek(ilac_ismi):
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin"}
    temiz = ilac_ismi.lower().strip()
    arama = sozluk.get(temiz, temiz).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac_ismi.upper()}: {d.get('indications_and_usage',[''])[0][:400]}"
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim")
    user_api_key = st.text_input("API Anahtarı", type="password", value=st.session_state.get("saved_key", ""))
    if user_api_key: st.session_state["saved_key"] = user_api_key

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")

if st.button("Hızlı Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. HAFIZA KONTROLÜ
        conn, df = hafizayi_getir()
        found = False
        if df is not None:
            existing = df[df['ilaclar'] == query_id]
            if not existing.empty:
                st.success("✅ Hafızadan getirildi!")
                st.markdown(existing.iloc[0]['rapor'])
                found = True

        if not found:
            # 2. YENİ ANALİZ
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("Yeni analiz için lütfen sol menüden API anahtarınızı girin.")
            else:
                with st.status("Analiz hazırlanıyor...", expanded=True) as status:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        results = list(executor.map(fda_verisi_cek, drugs))
                    
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        status.update(label="Hata: Veri bulunamadı!", state="error")
                    else:
                        try:
                            genai.configure(api_key=active_key)
                            model = genai.GenerativeModel('gemini-1.5-flash-8b') 
                            
                            prompt = f"Şu FDA verilerini doktor için kısa özetle ve etkileşim uyarısı yap: {fda_metni}"
                            response = model.generate_content(prompt, stream=True)
                            
                            placeholder = st.empty()
                            full_response = ""
                            for chunk in response:
                                full_response += chunk.text
                                placeholder.markdown(full_response + "▌")
                            
                            placeholder.markdown(full_response)
                            status.update(label="Analiz Tamamlandı!", state="complete")

                            # 3. HAFIZAYA KAYDET (HATA VERİRSE SİSTEMİ DURDURMAZ)
                            if conn is not None and df is not None:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [full_response]})
                                    df_updated = pd.concat([df, new_row], ignore_index=True)
                                    conn.update(data=df_updated)
                                except: pass # Kaydetme hatasını görmezden gel
                        except Exception as e:
                            st.error(f"Yapay Zeka Hatası: {str(e)}")
