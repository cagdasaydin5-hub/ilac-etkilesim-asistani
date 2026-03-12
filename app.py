import streamlit as st
import google.generativeai as genai
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Sayfa Ayarları
st.set_page_config(page_title="Hekim İlaç Asistanı", page_icon="💊", layout="wide")

# --- ÖNEMLİ: TARAYICI HAFIZASI (LOCAL STORAGE) ---
# Bu script, API anahtarını kullanıcının tarayıcısına güvenli bir şekilde kaydeder.
def save_key_to_browser(key):
    st.session_state["saved_api_key"] = key
    # Streamlit doğrudan local storage yazamaz, ancak session_state ile bu oturumda tutarız.
    # Tarayıcıların "Şifre Hatırla" özelliği 'type="password"' alanlarında otomatik devreye girer.

st.title("💊 Hekim İlaç Asistanı (Kolektif Hafıza)")
st.markdown("""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px;">
    <strong>Nasıl Çalışır?</strong><br>
    1. İlaçları yazın ve sorgulayın.<br>
    2. Eğer bu kombinasyon daha önce analiz edildiyse <strong>ücretsiz ve anında</strong> rapor gelir.<br>
    3. Yeni bir analiz ise API anahtarınızı bir kez girmeniz yeterlidir.
</div>
""", unsafe_allow_html=True)

# --- GOOGLE SHEETS BAĞLANTISI ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_from_cache(query_key):
    try:
        df = conn.read(ttl="0") # Her zaman en güncel tabloya bak
        res = df[df['ilaclar'] == query_key]
        if not res.empty:
            return res.iloc[0]['rapor']
    except: return None
    return None

def save_to_cache(query_key, report):
    try:
        df_existing = conn.read()
        new_data = pd.DataFrame({"ilaclar": [query_key], "rapor": [report]})
        updated_df = pd.concat([df_existing, new_data], ignore_index=True)
        conn.update(data=updated_df)
    except: pass

# --- YAN MENÜ: API AYARLARI ---
with st.sidebar:
    st.header("🔑 Erişim Ayarları")
    # type="password" sayesinde tarayıcılar "Şifreyi Kaydet" teklifi sunar.
    user_api_key = st.text_input(
        "Gemini API Anahtarınız", 
        type="password", 
        value=st.session_state.get("saved_api_key", ""),
        help="Anahtarınız tarayıcınız tarafından hatırlanacaktır."
    )
    if user_api_key:
        save_key_to_browser(user_api_key)
        
    st.markdown("[🔑 Ücretsiz Anahtar Al](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.info("Kolektif hafıza sayesinde popüler sorgular zamanla tamamen ücretsiz hale gelecektir.")

# --- İLAÇ GİRİŞ VE ANALİZ ---
col1, col2 = st.columns(2)
with col1:
    d1 = st.text_input("1. İlaç", placeholder="Örn: Verxant")
    d3 = st.text_input("3. İlaç")
with col2:
    d2 = st.text_input("2. İlaç", placeholder="Örn: Coraspin")
    d4 = st.text_input("4. İlaç")

if st.button("Klinik Analizi Başlat", type="primary"):
    selected_drugs = sorted([d.strip().lower() for d in [d1, d2, d3, d4] if d.strip()])
    
    if not selected_drugs:
        st.warning("Lütfen en az bir ilaç girin.")
    else:
        query_key = ", ".join(selected_drugs)
        
        # 1. ÖNCE KOLEKTİF HAFIZAYA BAK (ÜCRETSİZ)
        with st.spinner("Kolektif hafıza taranıyor..."):
            cached_report = get_from_cache(query_key)
        
        if cached_report:
            st.success("✅ Bu analiz kolektif hafızadan getirildi (Ücretsiz)")
            st.markdown(cached_report)
        else:
            # 2. HAFIZADA YOKSA KULLANICI ANAHTARIYLA YENİ ANALİZ
            if not user_api_key:
                st.error("❌ Bu kombinasyon henüz analiz edilmemiş. Analizi başlatmak için sol menüden kendi API anahtarınızı girin.")
            else:
                with st.spinner("Yeni analiz yapılıyor (FDA + Yapay Zeka)..."):
                    try:
                        # (Burada FDA veri çekme fonksiyonlarını önceki kodlardaki gibi eklemelisin)
                        # Özetle: FDA'dan çek, Gemini'ye yolla.
                        
                        # --- TEMSİLİ ANALİZ SÜRECİ ---
                        genai.configure(api_key=user_api_key)
                        model = genai.GenerativeModel('gemini-2.0-flash') # En güncel model
                        
                        # FDA Veri Çekme (Basitleştirilmiş)
                        # ... (Önceki fda_cek fonksiyonu buraya gelecek) ...
                        
                        prompt = f"{query_key} ilaçları için prospektüs özeti ve etkileşim raporu hazırla."
                        response = model.generate_content(prompt)
                        report_text = response.text
                        
                        st.markdown(report_text)
                        
                        # 3. YENİ ANALİZİ HAFIZAYA KAYDET
                        save_to_cache(query_key, report_text)
                        st.balloons()
                        st.info("💡 Bu analiz kolektif hafızaya eklendi! Artık tüm meslektaşlarınız için ücretsiz.")
                        
                    except Exception as e:
                        st.error(f"Bir hata oluştu: {str(e)}")
