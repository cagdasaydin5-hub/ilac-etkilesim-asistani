import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

# --- URL'DEN ANAHTAR OKUMA ---
if "key" in st.query_params:
    st.session_state["saved_key"] = st.query_params["key"]

st.title("💊 Hekim İlaç Asistanı (Kolektif Hafıza)")

# --- DARK MODE UYUMLU REHBER ---
with st.expander("❓ Sistem Nasıl Çalışır? (Kullanım Rehberi)", expanded=True):
    st.info("""
    - **Ücretsiz Erişim:** Daha önce analiz edilmiş ilaçlar hafızadan anında ve şifresiz gelir.
    - **Yeni Analiz:** İlk kez sorgulanan ilaçlar için kendi Gemini API anahtarınızı girmeniz istenir.
    - **Kolektif Katkı:** Yaptığınız her analiz sisteme kaydedilir ve tüm hekimler için ücretsiz olur.
    - **İpucu:** İlaç bulunamazsa lütfen **etken maddesini** (örn: Diclofenac) yazmayı deneyin.
    """)

# --- GOOGLE SHEETS BAĞLANTISI ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Veritabanı bağlantı hatası. Lütfen Secrets kısmını kontrol edin.")

def fda_verisi_cek(ilac_ismi):
    """FDA veritabanından veri çeker. Türkçe ticari isimleri İngilizce jenerik isimlere çevirir."""
    # TÜRKİYE'DE YAYGIN İLAÇLAR SÖZLÜĞÜ (Genişletildi)
    sozluk = {
        "parol": "acetaminophen", "minoset": "acetaminophen", "tamol": "acetaminophen",
        "coraspin": "aspirin", "ecopirin": "aspirin",
        "verxant": "secukinumab", 
        "augmentin": "amoxicillin", "klamoks": "amoxicillin", "amoklavin": "amoxicillin",
        "dikloron": "diclofenac", "voltaren": "diclofenac", "dolorex": "diclofenac",
        "arveles": "dexketoprofen", "dexday": "dexketoprofen",
        "apranax": "naproxen", "aprol": "naproxen",
        "majezic": "flurbiprofen",
        "buscopan": "hyoscine",
        "lansor": "lansoprazole",
        "beloc": "metoprolol",
        "lipitor": "atorvastatin",
        "glifor": "metformin", "matofin": "metformin"
    }
    
    # Türkçe karakter temizliği ve sözlük kontrolü
    temiz_isim = ilac_ismi.lower().replace('ı', 'i').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g').replace('ü', 'u').replace('ö', 'o')
    arama_terimi = sozluk.get(temiz_isim, temiz_isim).replace(" ", "+")
    
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama_terimi}"+OR+openfda.brand_name:"{arama_terimi}")&limit=1'
    try:
        response = requests.get(url, timeout=7)
        if response.status_code == 200:
            data = response.json()['results'][0]
            return f"""
            --- {ilac_ismi.upper()} ---
            Endikasyon: {data.get('indications_and_usage', [''])[0][:800]}
            Dozaj: {data.get('dosage_and_administration', [''])[0][:800]}
            Uyarılar: {data.get('warnings', data.get('boxed_warning', ['']))[0][:800]}
            Etkileşimler: {data.get('drug_interactions', [''])[0][:800]}
            """
    except: return None
    return None

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    current_key = st.text_input("Gemini API Anahtarınız", type="password", value=st.session_state.get("saved_key", ""))
    
    if current_key:
        st.session_state["saved_key"] = current_key
        
    if st.button("Şifremi bu linke göm ve hatırla"):
        st.query_params["key"] = current_key
        st.success("Link güncellendi! Sık kullanılanlara (Bookmark) eklemeyi unutmayın.")

    st.markdown("[🔑 Ücretsiz Anahtar Al](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.caption("Kolektif hafıza geliştikçe şifre gereksinimi azalacaktır.")

# --- GİRİŞ ALANLARI ---
col1, col2 = st.columns(2)
with col1:
    i1 = st.text_input("1. İlaç", placeholder="Örn: Dikloron")
    i3 = st.text_input("3. İlaç")
with col2:
    i2 = st.text_input("2. İlaç", placeholder="Örn: Coumadin")
    i4 = st.text_input("4. İlaç")

# --- ANALİZ ---
if st.button("Klinik Analizi Başlat", type="primary"):
    drugs = sorted([d.strip().lower() for d in [i1, i2, i3, i4] if d.strip()])
    
    if not drugs:
        st.warning("Lütfen en az bir ilaç girin.")
    else:
        query_id = ", ".join(drugs)
        
        # 1. HAFIZA KONTROLÜ
        with st.spinner("Hafıza taranıyor..."):
            try:
                df = conn.read(ttl="5s")
                existing = df[df['ilaclar'] == query_id]
                found = not existing.empty
            except: 
                found = False
                df = pd.DataFrame(columns=["ilaclar", "rapor"])
        
        if found:
            st.success("✅ Hafızadan getirildi (Ücretsiz)")
            st.markdown(existing.iloc[0]['rapor'])
        else:
            # 2. YENİ ANALİZ
            user_key = st.session_state.get("saved_key")
            if not user_key:
                st.error("❌ Bu kombinasyon hafızada yok. Lütfen sol menüden API anahtarınızı girin.")
            else:
                with st.spinner("FDA taranıyor ve rapor hazırlanıyor..."):
                    fda_metni = ""
                    for d in drugs:
                        m = fda_verisi_cek(d)
                        if m: fda_metni += m
                    
                    if not fda_metni:
                        st.error("İlaçlar FDA'da bulunamadı. Lütfen etken madde ismiyle (örn: Diclofenac) deneyin.")
                    else:
                        try:
                            genai.configure(api_key=user_api_key if 'user_api_key' in locals() else user_key)
                            model = genai.GenerativeModel('gemini-2.0-flash')
                            
                            prompt = f"""
                            Sen bir klinik farmakologsun. Sadece şu resmi FDA verilerini kullanarak Türkçe özet hazırla: {fda_metni}
                            
                            Rapor Formatı:
                            1. Etken Madde ve Sınıf
                            2. Pozoloji (Bebek, Çocuk, Yetişkin, Geriatrik ayrı ayrı)
                            3. Gebelik ve Emzirme Riskleri
                            4. Önemli Yan Etkiler ve Etkileşimler
                            
                            Not: Veride olmayan bilgiyi uydurma, 'Veri yok' de.
                            """
                            
                            response = model.generate_content(prompt, generation_config=genai.GenerationConfig(temperature=0.0))
                            rapor = response.text
                            st.markdown(rapor)
                            
                            # 3. KAYDET
                            new_row = pd.DataFrame({"ilaclar": [query_id], "rapor": [rapor]})
                            df_updated = pd.concat([df, new_row], ignore_index=True)
                            conn.update(data=df_updated)
                            st.info("💡 Hafızaya eklendi!")
                            
                        except Exception as e:
                            st.error(f"Hata: {str(e)}")
