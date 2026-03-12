import streamlit as st
import requests

st.set_page_config(page_title="İlaç Etkileşim Kontrolü", page_icon="💊")

st.title("💊 İlaç Etkileşim Kontrol Sistemi")
st.markdown("Reçetenizdeki ilaçların potansiyel etkileşimlerini **RxNav** altyapısıyla kontrol edin.")

ilac_sozlugu = {
    "parol": "paracetamol",
    "minoset": "paracetamol",
    "coraspin": "aspirin",
    "coumadin": "warfarin",
    "augmentin": "amoxicillin",
    "klamoks": "amoxicillin",
    "cipro": "ciprofloxacin",
    "beloc": "metoprolol",
    "desyrel": "trazodone",
    "lustral": "sertraline",
    "arveles": "dexketoprofen",
    "majezic": "flurbiprofen"
}

def etken_madde_bul(ticari_isim):
    temiz_isim = ticari_isim.strip().lower()
    return ilac_sozlugu.get(temiz_isim, temiz_isim)

# Kimliğimizi normal bir Windows/Chrome kullanıcısı gibi gösteriyoruz
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_rxcui(drug_name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'idGroup' in data and 'rxnormId' in data['idGroup']:
                return data['idGroup']['rxnormId'][0]
    except:
        pass
    return None

def check_interactions(rxcuis):
    if len(rxcuis) < 2:
        return None, "İki ilaç gerekli"
    
    cui_string = "+".join(rxcuis)
    url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={cui_string}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, f"Sunucu Hatası: {response.status_code}"
    except Exception as e:
        return None, f"Bağlantı Hatası: {str(e)}"

col1, col2 = st.columns(2)
with col1:
    drug1_input = st.text_input("1. İlaç (Örn: Coraspin)")
with col2:
    drug2_input = st.text_input("2. İlaç (Örn: Coumadin)")

if st.button("Etkileşimleri Kontrol Et", type="primary"):
    if drug1_input and drug2_input:
        with st.spinner('RxNav Veritabanı sorgulanıyor...'):
            etken1 = etken_madde_bul(drug1_input)
            etken2 = etken_madde_bul(drug2_input)
            
            st.info(f"🔍 Taranan Etken Maddeler: **{etken1.capitalize()}** ve **{etken2.capitalize()}**")
            
            cui1 = get_rxcui(etken1)
            cui2 = get_rxcui(etken2)
            
            if not cui1 or not cui2:
                st.error("Girdiğiniz ilaçlardan birinin etken maddesi sistemde bulunamadı.")
            else:
                interactions, error_msg = check_interactions([cui1, cui2])
                
                # Eğer bağlantı veya sunucu hatası alırsak tam sebebini ekrana yazdırıyoruz
                if error_msg:
                    st.error(f"⚠️ RxNav ile iletişim kurulamadı. Sebep: {error_msg}")
                elif interactions and 'fullInteractionTypeGroup' in interactions:
                    st.error("⚠️ DİKKAT: Etkileşim Tespit Edildi!")
                    for group in interactions['fullInteractionTypeGroup']:
                        for interaction in group['fullInteractionType']:
                            description = interaction['interactionPair'][0]['description']
                            st.write(f"- {description}")
                else:
                    st.success("✅ Bilinen bir majör etkileşim bulunamadı.")
    else:
        st.warning("Lütfen her iki kutuyu da doldurun.")
