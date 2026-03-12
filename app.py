import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hızlı Hekim Asistanı", page_icon="⚡", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("⚡ Hızlı Hekim Asistanı")

# --- GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def fda_verisi_cek(ilac_ismi):
    """FDA verilerini paralel çekmek için hızlandırılmış fonksiyon"""
    sozluk = {"dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin"}
    temiz = ilac_ismi.lower().strip()
    arama = sozluk.get(temiz, temiz).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac_ismi.upper()} FDA Kaydı:\n{d.get('indications_and_usage',[''])[0][:400]}\n"
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
        st.warning("İlaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. ADIM: HAFIZA KONTROLÜ (ÇOK HIZLI)
        df = conn.read(ttl="5s")
        existing = df[df['ilaclar'] == query_id]
        
        if not existing.empty:
            st.success("✅ Hafızadan getirildi!")
            st.markdown(existing.iloc[0]['rapor'])
        else:
            # 2. ADIM: YENİ ANALİZ
            active_key = st.session_state.get("saved_key")
            if not active_key:
                st.error("Yeni analiz için sol tarafa API anahtarı girmelisiniz.")
            else:
                # Durum çubuğu ile kullanıcıyı bilgilendiriyoruz
                with st.status("Analiz hazırlanıyor...", expanded=True) as status:
                    st.write("🔍 FDA veritabanı taranıyor...")
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        results = list(executor.map(fda_verisi_cek, drugs))
                    
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        status.update(label="Hata: Veri bulunamadı!", state="error")
                    else:
                        st.write("🧠 Yapay zeka raporu oluşturuyor...")
                        try:
                            genai.configure(api_key=active_key)
                            model = genai.GenerativeModel('gemini-1.5-flash-8b') 
                            
                            prompt = f"Şu FDA verilerini doktor için çok kısa özetle ve etkileşim uyarısı yap: {fda_metni}"
                            
                            # CANLI YAZIM (STREAMING) BURADA BAŞLIYOR
                            status.update(label="Analiz Tamamlanıyor...", state="running")
                            response = model.generate_content(prompt, stream=True)
                            
                            # Boş bir alan oluşturup cevabı oraya akıtıyoruz
                            placeholder = st.empty()
                            full_response = ""
                            for chunk in response:
                                full_response += chunk.text
                                placeholder.markdown(full_response + "▌") # İmleç efekti
                            
                            placeholder.markdown(full_response) # Final hali
                            status.update(label="Analiz Tamamlandı ve Kaydediliyor!", state="complete")

                            # 3. ADIM: KAYIT İŞLEMİ (EN SONDA)
                            new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [full_response]})
                            df_updated = pd.concat([df, new_row], ignore_index=True)
                            conn.update(data=df_updated)
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
