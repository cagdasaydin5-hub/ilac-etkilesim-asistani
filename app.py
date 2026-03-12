import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

# --- URL'DEN ANAHTAR OKUMA (OTOMATİK HATIRLAMA) ---
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("💊 Hekim İlaç Asistanı (Kolektif Hafıza)")

# --- DARK MODE UYUMLU BİLGİ KUTUSU ---
with st.expander("❓ Sistem Nasıl Çalışır? (Okumak için tıklayın)", expanded=True):
    st.info("""
    - **Ücretsiz Erişim:** Daha önce bir meslektaşınız tarafından analiz edilmiş ilaçlar hafızadan anında ve şifresiz gelir.
    - **Yeni Analiz:** Eğer ilaç kombinasyonu ilk kez sorgulanıyorsa, kendi Gemini API anahtarınızı girmeniz gerekir.
    - **Kolektif Katkı:** Yaptığınız her yeni analiz sisteme kaydedilir ve sizden sonraki tüm doktorlar için ücretsiz olur.
    """)

# --- GOOGLE SHEETS BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Google Sheets bağlantısı kurulamadı. Lütfen Secrets ayarlarını kontrol edin.")

def fda_verisi_cek(ilac_ismi):
    """FDA veritabanından ham prospektüs verisini çeker"""
    sozluk = {
        "parol": "acetaminophen", "minoset": "acetaminophen", 
        "coraspin": "aspirin", "verxant": "secukinumab", 
        "augmentin": "amoxicillin", "klamoks": "amoxicillin",
        "majezic": "flurbiprofen", "aprol": "naproxen"
    }
    arama = sozluk.get(ilac_ismi.lower(), ilac_ismi).replace(" ", "+")
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama}"+OR+openfda.brand_name:"{arama}")&limit=1'
    try:
        response = requests.get(url, timeout=7)
        if response.status_code == 200:
            data = response.json()['results'][0]
            return f"""
            --- {ilac_ismi.upper()} RESMİ VERİSİ ---
            Endikasyon: {data.get('indications_and_usage', [''])[0][:800]}
            Dozaj: {data.get('dosage_and_administration', [''])[0][:800]}
            Uyarılar: {data.get('warnings', data.get('boxed_warning', ['']))[0][:800]}
            Etkileşimler: {data.get('drug_interactions', [''])[0][:800]}
            """
    except: return None
    return None

# --- YAN MENÜ: ERİŞİM VE HATIRLATICI ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    current_key = st.text_input(
        "Gemini API Anahtarınız", 
        type="password", 
        value=st.session_state.get("saved_key", ""),
        help="Anahtarınız tarayıcınızda güvenle saklanacaktır."
    )
    if current_key:
        st.session_state["saved_key"] = current_key
        
    if st.button("Şifremi bu linke göm ve hatırla"):
        st.query_params["key"] = current_key
        st.success("Link güncellendi! Sayfayı 'Sık Kullanılanlara' eklerseniz anahtarınız otomatik yüklenecektir.")

    st.markdown("[🔑 Ücretsiz Anahtar Al](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("Kolektif hafıza sayesinde sistem zamanla tamamen ücretsiz hale gelecektir.")

# --- İLAÇ GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Arveles")
    i3 = st.text_input("3. İlaç")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Coraspin")
    i4 = st.text_input("4. İlaç")

# --- ANALİZ MANTIĞI ---
if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen analiz için en az bir ilaç ismi girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. KOLEKTİF HAFIZA KONTROLÜ
        with st.spinner("Kolektif hafıza taranıyor..."):
            try:
                df = conn.read(ttl="5s")
                existing = df[df['ilaclar'] == query_id]
                found = not existing.empty
            except: 
                found = False
                df = pd.DataFrame(columns=["ilaclar", "rapor"])
        
        if found:
            st.success("✅ Bu analiz kolektif hafızadan getirildi (Ücretsiz)")
            st.markdown(existing.iloc[0]['rapor'])
        else:
            # 2. HAFIZADA YOKSA YENİ ANALİZ
            if not st.session_state.get("saved_key"):
                st.error("❌ Bu kombinasyon henüz analiz edilmemiş. Lütfen sol menüden API anahtarınızı girin.")
            else:
                with st.spinner("FDA verileri çekiliyor ve YZ raporu hazırlanıyor..."):
                    fda_metni = ""
                    for d in drugs:
                        m = fda_verisi_cek(d)
                        if m: fda_metni += m
                    
                    if not fda_metni:
                        st.error("Girdiğiniz ilaçlar FDA veritabanında bulunamadı. Lütfen etken maddeyi kontrol edin.")
                    else:
                        try:
                            genai.configure(api_key=st.session_state["saved_key"])
                            model = genai.GenerativeModel('gemini-2.0-flash')
                            
                            prompt = f"""
                            Sen uzman bir klinik farmakologsun. Sadece şu resmi FDA verilerini kullanarak Türkçe özet hazırla:
                            {fda_metni}
                            
                            Rapor Formatı:
                            1. Etken Madde ve Sınıf
                            2. Pozoloji (Bebek, Çocuk, Yetişkin, Geriatrik - Ayrı başlıklarla ve veride varsa mg/kg hesabı ile)
                            3. Gebelik ve Emzirme Riskleri (Kategori belirterek)
                            4. Önemli Yan Etkiler ve İlaç Etkileşimleri
                            
                            Önemli: Veride olmayan bilgiyi asla uydurma, 'Veri yok' de.
                            """
                            
                            # 429 Hatası için basit bir retry (tekrar deneme)
                            for attempt in range(2):
                                try:
                                    response = model.generate_content(prompt, generation_config=genai.GenerationConfig(temperature=0.0))
                                    rapor = response.text
                                    st.markdown(rapor)
                                    
                                    # 3. YENİ ANALİZİ HAFIZAYA KAYDET
                                    new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [rapor]})
                                    df_updated = pd.concat([df, new_row], ignore_index=True)
                                    conn.update(data=df_updated)
                                    st.balloons()
                                    st.info("💡 Analiz tamamlandı ve kolektif hafızaya kaydedildi!")
                                    break
                                except Exception as e:
                                    if "429" in str(e) and attempt == 0:
                                        time.sleep(3)
                                        continue
                                    else: raise e
                        except Exception as e:
                            st.error(f"Bir hata oluştu: {str(e)}")
