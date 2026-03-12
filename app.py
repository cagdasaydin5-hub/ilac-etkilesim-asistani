import streamlit as st
import google.generativeai as genai
import requests

st.set_page_config(page_title="Güvenli İlaç Asistanı", page_icon="🛡️", layout="wide")

st.title("🛡️ %100 Doğrulanmış İlaç Asistanı (RAG Mimarisi)")
st.markdown("Bu sistem yapay zekanın uydurmasını engellemek için önce **Amerikan FDA Veritabanından** ilacın gerçek prospektüsünü çeker, ardından yapay zeka sadece bu çekilen veriyi baz alarak analiz yapar.")

# API anahtarını gizli kasadan çekiyoruz
api_key = st.secrets["GEMINI_API_KEY"]

# FDA'nın tanıması için yaygın ticari ilaçların etken madde karşılıkları
# Not: Parol'un etken maddesi FDA'da 'acetaminophen' olarak geçer, o yüzden onu güncelledik.
ilac_sozlugu = {
    "parol": "acetaminophen",
    "minoset": "acetaminophen",
    "coraspin": "aspirin",
    "coumadin": "warfarin",
    "augmentin": "amoxicillin",
    "klamoks": "amoxicillin",
    "cipro": "ciprofloxacin",
    "beloc": "metoprolol",
    "desyrel": "trazodone",
    "lustral": "sertraline",
    "majezic": "flurbiprofen",
    "verxant": "secukinumab" 
}

def etken_madde_bul(ticari_isim):
    temiz_isim = ticari_isim.strip().lower()
    return ilac_sozlugu.get(temiz_isim, temiz_isim)

# 1. AŞAMA: FDA'DAN RESMİ VERİ ÇEKME FONKSİYONU
def fda_verisi_cek(etken_madde):
    arama_terimi = etken_madde.replace(" ", "+")
    # FDA veritabanında hem jenerik hem de marka isminde arama yapıyoruz
    url = f'https://api.fda.gov/drug/label.json?search=(openfda.generic_name:"{arama_terimi}"+OR+openfda.brand_name:"{arama_terimi}")&limit=1'
    
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()['results'][0]
            
            # FDA verisinden ilgili başlıkları ham olarak alıyoruz (Yapay zeka boğulmasın diye 1500 karakterle sınırlıyoruz)
            endikasyon = data.get('indications_and_usage', ['Belirtilmemiş'])[0]
            doz = data.get('dosage_and_administration', ['Belirtilmemiş'])[0]
            uyarilar = data.get('warnings', data.get('boxed_warning', ['Belirtilmemiş']))[0]
            etkilesimler = data.get('drug_interactions', ['Belirtilmemiş'])[0]
            
            return f"""
            --- {etken_madde.upper()} İÇİN RESMİ FDA VERİSİ ---
            Endikasyonlar: {endikasyon[:1500]}
            Dozaj: {doz[:1500]}
            Uyarılar: {uyarilar[:1500]}
            Etkileşimler: {etkilesimler[:1500]}
            -------------------------------------
            """
    except Exception:
        return None
    return None


st.subheader("İlaç Listesi")
col1, col2 = st.columns(2)
with col1:
    ilac1 = st.text_input("1. İlaç", placeholder="Örn: Verxant")
    ilac3 = st.text_input("3. İlaç")
with col2:
    ilac2 = st.text_input("2. İlaç", placeholder="Örn: Coraspin")
    ilac4 = st.text_input("4. İlaç")

if st.button("Güvenli Analiz Et", type="primary"):
    ilac_listesi = [ilac1, ilac2, ilac3, ilac4]
    girilen_ilaclar = [ilac.strip() for ilac in ilac_listesi if ilac.strip()]
    
    if len(girilen_ilaclar) < 1:
        st.warning("Lütfen analiz için en az 1 ilaç girin.")
    else:
        # ÖNCE DOĞRULAMA (RAG MİMARİSİ)
        with st.spinner('1/2: Resmi FDA veritabanı taranıyor ve ham veri çekiliyor...'):
            dogrulanan_veriler = ""
            hatali_ilaclar = []
            
            for ilac in girilen_ilaclar:
                etken = etken_madde_bul(ilac)
                fda_metni = fda_verisi_cek(etken)
                
                if fda_metni:
                    dogrulanan_veriler += fda_metni + "\n"
                else:
                    hatali_ilaclar.append(ilac)
            
        # Eğer FDA'da bulamadığı tek bir ilaç bile varsa sistemi kilitliyoruz
        if hatali_ilaclar:
            st.error(f"🛑 GÜVENLİK İHLALİ: '{', '.join(hatali_ilaclar)}' isimli ilaç(lar) resmi FDA veritabanında doğrulanamadı. Yapay zekanın veri uydurmasını (halüsinasyon) önlemek için analiz tamamen durduruldu. Lütfen etken maddeyi İngilizce yazmayı deneyin.")
        
        else:
            # 2. AŞAMA: YAPAY ZEKANIN SADECE ÇEKİLEN VERİYİ ÖZETLEMESİ
            with st.spinner('2/2: Çekilen resmi veriler yapay zekaya aktarılıyor ve klinik rapora dönüştürülüyor...'):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash') 
                    
                    # PROMPT: Yapay zekanın kendi hafızasını kullanmasını KESİN OLARAK yasaklıyoruz.
                    prompt = f"""
                    Sen uzman bir klinik farmakologsun. SANA AŞAĞIDA AMERİKAN FDA (Gıda ve İlaç Dairesi) TARAFINDAN ONAYLANMIŞ RESMİ PROSPEKTÜS METİNLERİNİ VERİYORUM.
                    
                    RESMİ VERİ:
                    {dogrulanan_veriler}
                    
                    GÖREVİN VE KESİN KURALLARIN: 
                    SADECE ve SADECE yukarıda sana verdiğim "RESMİ VERİ" metnini kullanarak doktor için Türkçe bir özet rapor hazırlayacaksın.
                    Kendi hafızandan, genel tıp bilginden veya internetten HİÇBİR ŞEY EKLEME. 
                    Eğer resmi verinin içinde örneğin "Bebek dozu" yazmıyorsa uydurma, doğrudan "Resmi FDA metninde veri yok" yaz.
                    
                    Lütfen şu formatta çok kısa madde işaretleriyle raporu sun:
                    1. Endikasyon ve Kullanım
                    2. Yaş Gruplarına Göre Pozoloji (Veride varsa)
                    3. Kritik Uyarılar (Kara Kutu uyarıları varsa belirt)
                    4. Etkileşimler (Eğer birden fazla ilaç varsa ve veri birbirleriyle etkileşim gösteriyorsa)
                    """
                    
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(temperature=0.0) # Yaratıcılık Sıfır!
                    )
                    
                    st.success("✅ Güvenli Analiz Tamamlandı (Kaynak: Amerikan FDA)")
                    st.markdown("### 📋 Doğrulanmış Klinik Rapor")
                    st.write(response.text)
                    
                except Exception as e:
                    st.error(f"Yapay Zeka Hata Detayı: {str(e)}")
