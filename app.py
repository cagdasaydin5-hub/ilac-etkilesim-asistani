import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Kapsamlı İlaç Asistanı", page_icon="💊", layout="wide")

st.title("💊 YZ Destekli Kapsamlı İlaç Asistanı")
st.markdown("Reçetenizdeki ilaçların etken maddesini, gebelik/emzirme risklerini, yaş gruplarına göre pozolojisini ve etkileşimlerini saniyeler içinde analiz edin.")

# API anahtarını gizli kasadan çekiyoruz
api_key = st.secrets["GEMINI_API_KEY"]

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

if st.button("Kapsamlı Analiz Et", type="primary"):
    ilac_listesi = [ilac1, ilac2, ilac3, ilac4, ilac5]
    girilen_ilaclar = [ilac.strip() for ilac in ilac_listesi if ilac.strip()]
    
    if len(girilen_ilaclar) < 1:
        st.warning("Lütfen analiz için en az 1 ilaç girin.")
    else:
        with st.spinner('Literatür taraması yapıyorum, lütfen bekleyin...'):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash') 
                
                # GÜNCELLENEN KISIM: Pozoloji başlığını yaş gruplarına göre detaylandırdık
                prompt = f"""
                Sen uzman bir klinik farmakologsun. Aşağıdaki ilaçlar için klinik bir rehber (kısa prospektüs özeti) hazırlaman gerekiyor:
                İlaçlar: {', '.join(girilen_ilaclar)}
                
                Lütfen klinik şartlarda hızlıca okunabilecek, gereksiz kelimelerden arındırılmış, madde işaretli bir rapor sun. Rapor kesinlikle şu başlıkları içermelidir:
                
                **1. ETKEN MADDE VE SINIF:**
                Girilen her ilacın etken maddesini ve farmakolojik sınıfını kısaca belirt.
                
                **2. YAŞ GRUPLARINA GÖRE POZOLOJİ VE ENDİKASYON:**
                İlacın temel endikasyonunu yaz. Ardından kullanım sıklığını ve dozajını şu gruplar için ayrı ayrı, net bir şekilde belirt (kilo bazlı hesaplamalar varsa kg başına dozu ekle):
                - Bebek / Süt Çocukluğu
                - Çocuk
                - Yetişkin
                - Geriatrik
                (Eğer ilaç belirli bir yaş grubu için kontrendike ise veya veri yoksa bunu açıkça vurgula.)
                
                **3. GEBELİK VE EMZİRME RİSKİ:**
                Gebelik risk kategorisini (A, B, C, D, X) ve emzirme döneminde kullanım güvenliğini kesin bir dille belirt. Riskli veya kontrendike durumlarda ⚠️ emojisi kullan.
                
                **4. ÖNEMLİ KONTRENDİKASYONLAR VE YAN ETKİLER:**
                İlacın kesinlikle kullanılmaması gereken ana durumları ve en sık/en tehlikeli 2-3 yan etkiyi kısaca listele.
                
                **5. ETKİLEŞİM ANALİZİ (Eğer birden fazla ilaç girildiyse):**
                Bu ilaçlar arasındaki potansiyel etkileşimleri analiz et. Ölümcül veya çok riskli bir etkileşim varsa 🛑 emojisiyle en başta uyar.
                """
                
                response = model.generate_content(prompt)
                
                st.success("✅ Analiz Tamamlandı")
                st.markdown("### 📋 Kapsamlı Klinik Rapor")
                st.write(response.text)
                
            except Exception as e:
                st.error(f"Hata Detayı: {str(e)}")
