import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- AYARLAR ---
st.set_page_config(page_title="Hekim İlaç Asistanı 2026", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Hekim İlaç Asistanı v4.0")

# --- VERİTABANI BAĞLANTISI (HİÇBİR ŞARTTA ÇÖKMEZ) ---
@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

# --- FDA VERİ ÇEKME ---
def fda_verisi_cek(ilac):
    sozluk = {"dikloron": "diclofenac", "voltaren": "diclofenac", "parol": "acetaminophen", "arveles": "dexketoprofen"}
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json()['results'][0]
            return f"{ilac.upper()}:\nEndikasyon: {d.get('indications_and_usage',[''])[0][:400]}\nDozaj: {d.get('dosage_and_administration',[''])[0][:400]}"
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    
    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = key
        st.success("Link güncellendi! Bookmark yapın.")
    
    st.divider()
    st.info("Limit Hatası (429) alırsanız 1 dakika bekleyin. Kolektif hafıza doldukça sistem tamamen ücretsizleşecektir.")

# --- ANA EKRAN ---
i1 = st.text_input("1. İlaç (Örn: Dikloron)")
i2 = st.text_input("2. İlaç (Örn: Coumadin)")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. ADIM: HAFIZA KONTROLÜ
        conn = get_db()
        found_rapor = None
        if conn:
            try:
                df = conn.read(ttl="10s")
                res = df[df['ilaclar'] == query_id]
                if not res.empty: found_rapor = res.iloc[0]['rapor']
            except: pass

        if found_rapor:
            st.success("✅ Hafızadan getirildi (Limit harcamaz)")
            st.markdown(found_rapor)
        else:
            # 2. ADIM: YENİ ANALİZ
            if not st.session_state.get("saved_key"):
                st.error("Yeni analiz için API Key gerekli.")
            else:
                with st.spinner("2026 Modelleri taranıyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as ex:
                        results = list(ex.map(fda_verisi_cek, drugs))
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA verisi bulunamadı.")
                    else:
                        # SENİN LİSTENDEN EN STABİL MODELLER
                        model_siralamasi = ['gemini-2.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro-latest']
                        final_response = None
                        
                        genai.configure(api_key=st.session_state["saved_key"])
                        
                        for m_name in model_siralamasi:
                            try:
                                model = genai.GenerativeModel(m_name)
                                response = model.generate_content(f"Doktor için kısa Türkçe özet ve etkileşim raporu: {fda_metni}")
                                final_response = response.text
                                break
                            except Exception as e:
                                if "429" in str(e): # Kota hatası
                                    continue 
                                elif "404" in str(e): # Model yok hatası
                                    continue
                                else:
                                    st.error(f"Hata ({m_name}): {str(e)}")
                        
                        if final_response:
                            st.markdown(final_response)
                            # 3. ADIM: SESSİZ KAYIT
                            if conn:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [final_response]})
                                    conn.update(data=pd.concat([df, new_row], ignore_index=True))
                                except: pass
                        else:
                            st.error("Şu an tüm modeller yoğun veya kotanız dolmuş. Lütfen biraz sonra tekrar deneyin.")
