import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="YZ İlaç Etkileşim Asistanı", page_icon="🤖", layout="wide")

st.title("🤖 YZ Destekli İlaç Etkileşim Kontrolü")
st.markdown("Reçetenizdeki 5 farklı ilaca kadar potansiyel etkileşimleri saniyeler içinde analiz edin.")

# Sol Menü - API Anahtarı Girişi
st.sidebar.header("⚙️ Sistem Ayarları")
st.sidebar.markdown("Yapay zekanın çalışması için ücretsiz Gemini API anahtarınızı girin.")
api_key = st.sidebar.text_input("API Anahtarı", type="password")
st.sidebar.markdown("[🔑 Ücretsiz API Anahtarı Almak İçin Tıklayın](https://aistudio.google.com/app/apikey)")
st.sidebar.info("Güvenlik notu: Girdiğiniz anahtar hiçbir yere kaydedilmez, sadece bu seans için geçerlidir.")

# 5 İlaç için düzenli giriş kutuları
st.subheader("İlaç Listesi")
col1, col2 = st.columns(2)
with col1:
    ilac1 = st.text_input("1. İlaç", placeholder="Örn: Coraspin")
    ilac3 = st.text_input("3. İlaç")
    ilac5 = st.text_input("5. İlaç")
with col2:
    ilac2 = st.text_input("2. İlaç", placeholder="Örn: Coumadin")
    ilac4 = st.text_input("4. İlaç")

if st.button("Yapay Zeka ile Analiz Et", type="primary"):
    if not api_key:
        st.error("Lütfen sol menüden Gemini API anahtarınızı girin.")
    else:
        # Girilen ilaçları topla ve boş olanları filtrele
        ilac_listesi = [ilac1, ilac2, ilac3, ilac4, ilac5]
        girilen_ilaclar = [ilac.strip() for ilac in ilac_listesi if ilac.strip()]
        
        if len(girilen_ilaclar) < 2:
            st.warning("Etkileşim analizi için en az 2 ilaç girmelisiniz.")
        else:
            with st.spinner('Yapay zeka tıp literatürünü tarıyor, lütfen bekleyin...'):
                try:
                    # Yapay Zeka Bağlantısını Kur
                    genai.configure(api_key=api_key)
                    # En hızlı ve güncel model
                    model = genai.GenerativeModel('gemini-1.5-flash') 
                    
                    # Yapay zekaya verdiğimiz gizli komut (Prompt)
                    prompt = f"""
                    Sen uzman bir klinik farmakologsun. Bir hekim aşağıdaki ilaçları aynı hastaya reçete etmeyi düşünüyor:
                    İlaçlar: {', '.join(girilen_ilaclar)}
                    
                    Lütfen bu ilaçlar arasındaki potansiyel majör ve minör etkileşimleri analiz et.
                    Eğer çok tehlikeli (kontrendike) bir durum varsa kırmızı bayrakla kesin bir dille uyar.
                    Kısa, net ve poliklinik şartlarında hızlıca okunabilecek madde işaretli bir rapor sun.
                    Gereksiz uzatmalardan kaçın. Sadece kanıta dayalı tıbbi gerçeklere odaklan.
                    """
                    
                    response = model.generate_content(prompt)
                    
                    st.success("✅ Analiz Tamamlandı")
                    st.markdown("### 📋 Etkileşim Raporu")
                    st.write(response.text)
                    
                except Exception as e:
                    st.error(f"Yapay zeka ile iletişimde bir hata oluştu. Lütfen API anahtarınızı kontrol edin.")
