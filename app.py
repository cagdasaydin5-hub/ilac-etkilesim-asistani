import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="YZ İlaç Etkileşim Asistanı", page_icon="🤖", layout="wide")

st.title("🤖 YZ Destekli İlaç Etkileşim Kontrolü")
st.markdown("Reçetenizdeki 5 farklı ilaca kadar potansiyel etkileşimleri saniyeler içinde analiz edin.")

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

if st.button("Yapay Zeka ile Analiz Et", type="primary"):
    ilac_listesi = [ilac1, ilac2, ilac3, ilac4, ilac5]
    girilen_ilaclar = [ilac.strip() for ilac in ilac_listesi if ilac.strip()]
    
    if len(girilen_ilaclar) < 2:
        st.warning("Etkileşim analizi için en az 2 ilaç girmelisiniz.")
    else:
        with st.spinner('Yapay zeka tıp literatürünü tarıyor, lütfen bekleyin...'):
            try:
                genai.configure(api_key=api_key)
                
                # GÜNCELLENEN KISIM: Model ismini en stabil versiyon olan 'gemini-pro' yaptık
                model = genai.GenerativeModel('gemini-pro') 
                
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
                st.error(f"Hata Detayı: {str(e)}")
