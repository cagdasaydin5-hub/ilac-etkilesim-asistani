import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
import concurrent.futures

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="🛡️", layout="wide")

if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("🛡️ Klinik Karar Destek (v9.6)")
st.info("💡 **İpucu:** İlaçları yazıp 'Analiz'e basın. TİTCK (KÜB/KT) standartlarına göre yerel bir özet sunulacaktır.")

# --- FDA VERİ ÇEKME ---
def fda_verisi_cek(ilac):
    sozluk = {
        "dikloron": "diclofenac", "parol": "acetaminophen", "coraspin": "aspirin", 
        "coumadin": "warfarin", "augmentin": "amoxicillin", "arveles": "dexketoprofen"
    }
    arama = sozluk.get(ilac.lower().strip(), ilac).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=5'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            res = r.json()['results']
            metin = f"\n--- {ilac.upper()} ---\n"
            for d in res:
                metin += f"Doz: {d.get('dosage_and_administration',[''])[0][:600]}\n"
                metin += f"Etkileşim: {d.get('drug_interactions',[''])[0][:500]}\n"
            return metin
    except: return None
    return None

# --- YAN MENÜ (API AYARLARI VE AÇIKLAMA) ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    st.markdown("""
    Sistemin çalışması için bir **Gemini API Key** gereklidir. 
    Anahtarınız yoksa aşağıdaki linkten tamamen ücretsiz alabilirsiniz:
    
    👉 [Google AI Studio - API Key Al](https://aistudio.google.com/app/apikey)
    """)
    
    key = st.text_input("Gemini API Key Girin", type="password", value=st.session_state.get("saved_key", ""))
    if key: st.session_state["saved_key"] = key
    
    if st.button("Şifreyi Linke Göm (Hızlı Erişim)"):
        st.query_params["key"] = key
        st.success("Link güncellendi! Sayfayı bookmark yapabilirsiniz.")
    
    st.divider()
    st.caption("Not: Bu uygulama verileri FDA'dan çeker ve Gemini 2.5 ile Türkiye TİTCK standartlarına göre yorumlar.")

# --- 4 İLAÇ GİRİŞİ ---
st.subheader("💊 İlaç Listesi (Maks 4)")
c1, c2, c3, c4 = st.columns(4)
with c1: i1 = st.text_input("1. İlaç")
with c2: i2 = st.text_input("2. İlaç")
with c3: i3 = st.text_input("3. İlaç")
with c4: i4 = st.text_input("4. İlaç")

if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = [d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()]
    if not drugs:
        st.warning("En az bir ilaç ismi girin.")
    else:
        active_key = st.session_state.get("saved_key")
        if not active_key:
            st.error("Lütfen sol menüden API Key giriniz.")
        else:
            with st.spinner("TİTCK standartlarına göre çapraz analiz yapılıyor..."):
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    results = list(ex.map(fda_verisi_cek, drugs))
                
                fda_metni = "\n".join([r for r in results if r])
                
                try:
                    genai.configure(api_key=active_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # --- <br> VE HTML TEMİZLİĞİ İÇİN SERT PROMPT ---
                    prompt = f"""
                    Sen Türkiye'de çalışan uzman bir klinik farmakologsun. 
                    Aşağıdaki verileri TİTCK (KÜB/KT) rehberlerine göre yorumla.

                    ### ⚠️ KRİTİK ETKİLEŞİM UYARISI
                    - {', '.join(drugs)} ilaçlarının arasındaki çapraz etkileşim risklerini belirt.

                    ### 📋 TİTCK STANDARTLI POZOLOJİ TABLOSU
                    | İlaç | Endikasyon (TR) | Dozaj (Oral/IM/IV) | Çocuk/Yaşlı Dozu | Gebelik |
                    | :--- | :--- | :--- | :--- | :--- |

                    KESİN KURALLAR:
                    1. ASLA HTML kodu (<br>, <b>, <font> vb.) kullanma. Alt satıra geçmek için sadece normal Enter (satır başı) kullan.
                    2. Giriş/sonuç cümlesi yazma. Doğrudan tabloyu ve uyarıyı ver.
                    3. Pozolojide "Aç/Tok" bilgisini mutlaka ekle.
                    4. Topikalleri (jel, krem) pas geç, sistemik formlara odaklan.
                    
                    VERİLER:
                    {fda_metni}
                    """

                    response = model.generate_content(prompt)
                    # Buradaki .replace, AI yanlışlıkla kod üretirse son bir temizlik yapar
                    temiz_yanit = response.text.replace("<br>", "\n").replace("<br/>", "\n")
                    st.markdown(temiz_yanit)
                    
                except Exception as e:
                    st.error(f"Hata: {str(e)}")
