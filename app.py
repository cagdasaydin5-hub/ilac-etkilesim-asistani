import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı 2026", page_icon="💊", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

# --- BAŞLIK VE UYARI ---
st.title("🛡️ Hekim İlaç Asistanı v4.5")
st.error("⚠️ **DİKKAT:** Bu bir yapay zeka özetidir. Klinik karar ve doz doğrulaması tamamen hekimin sorumluluğundadır.")

# --- VERİTABANI VE FDA SORGUSU ---
@st.cache_resource
def get_db():
    try: return st.connection("gsheets", type=GSheetsConnection)
    except: return None

def fda_verisi_cek(ilac):
    sozluk = {
        "dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin",
        "augmentin": "amoxicillin", "arveles": "dexketoprofen", "klamoks": "amoxicillin"
    }
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    # Farklı formları yakalamak için limit=3
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=3'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = ""
            for d in res:
                metin += f"\n--- {ilac.upper()} VERİSİ ---\n"
                metin += f"Endikasyon: {d.get('indications_and_usage',[''])[0][:300]}\n"
                metin += f"Dozaj: {d.get('dosage_and_administration',[''])[0][:500]}\n"
            return metin
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    key = st.text_input("Gemini API Key", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    if st.button("Şifreyi Linke Göm"):
        st.query_params["key"] = key
        st.success("Link güncellendi!")

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1: i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
with col2: i2 = st.text_input("2. İlaç", placeholder="Örn: Parol")

# --- ANALİZ MANTIĞI ---
if st.button("Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2] if d.strip()])
    if not drugs:
        st.warning("Lütfen ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        conn = get_db()
        found_rapor = None
        
        # 1. HAFIZA KONTROLÜ
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
                st.error("Yeni analiz için API Key gerekli.")
            else:
                with st.spinner("Klinik veriler süzülüyor..."):
                    with concurrent.futures.ThreadPoolExecutor() as ex:
                        results = list(ex.map(fda_verisi_cek, drugs))
                    fda_metni = "\n".join([r for r in results if r])
                    
                    if not fda_metni:
                        st.error("FDA veritabanında bilgi bulunamadı.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            # --- TAM VE SERT PROMPT (Burası işin beyni) ---
                            prompt = f"""
                            Sen bir Aile Hekimi asistanısın. Aşağıdaki FDA verilerini, bir doktorun poliklinikte 10 saniyede okuyabileceği bir 'Klinik Karar Notu' haline getir.

                            KESİN KURALLAR:
                            1. GİRİŞ/SONUÇ YASAK: "Sayın Doktor", "Raporunuz hazır" gibi cümleleri ASLA kullanma. Direkt bilgiye geç.
                            2. TABLET SAYISI YASAK: Dozajı asla "X tablet" diye verme. Sadece MG veya MG/KG birimlerini kullan.
                            3. PEDİATRİK DOZ: Veride varsa, çocuklar için mg/kg/gün dozunu ve günlük doz limitini (Max mg/gün) mutlaka belirt.
                            4. GEBELİK/EMZİRME: Gebelik kategorisini (A,B,C,D,X) en başa kalın harflerle yaz.
                            5. DİL: Profesyonel tıp dili kullan. Gereksiz hiçbir kelime yazma.

                            FDA VERİLERİ:
                            {fda_metni}
                            """

                            response = model.generate_content(prompt)
                            final_rapor = response.text
                            st.markdown(final_rapor)
                            
                            # KAYIT
                            if conn:
                                try:
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [final_rapor]})
                                    conn.update(data=pd.concat([df, new_row], ignore_index=True))
                                except: pass
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
