import streamlit as st
import requests

# Web sayfasının sekme adını ve ikonunu belirliyoruz
st.set_page_config(page_title="İlaç Etkileşim Kontrolü", page_icon="💊")

st.title("💊 İlaç Etkileşim Kontrol Sistemi")
st.markdown("Reçetenizdeki ilaçların potansiyel etkileşimlerini **RxNav** altyapısıyla kontrol edin.")

# Sık kullanılan ilaçlar sözlüğü
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

def get_rxcui(drug_name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name}"
    try:
        # Sunucu takılırsa 5 saniye sonra iptal et
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'idGroup' in data and 'rxnormId' in data['idGroup']:
                return data['idGroup']['rxnormId'][0]
    except:
        pass
    return None

def check_interactions(rxcuis):
    if len(rxcuis) < 2:
        return None
    cui_string = "+".join(rxcuis)
    url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={cui_string}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

# Arama kutularını yan yana koyalım
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
                st.error("Girdiğiniz ilaçlardan birinin etken maddesi sistemde bulunamadı. İngilizce etken madde yazmayı deneyin.")
            else:
                interactions = check_interactions([cui1, cui2])
                
                # GÜNCELLENEN KISIM: Veri boş mu diye kontrol ediyoruz.
                if interactions is None:
                    st.error("RxNav sunucusuna bağlanılamadı veya yanıt alınamadı. Lütfen tekrar deneyin.")
                elif 'fullInteractionTypeGroup' in interactions:
                    st.error("⚠️ DİKKAT: Etkileşim Tespit Edildi!")
                    for group in interactions['fullInteractionTypeGroup']:
                        for interaction in group['fullInteractionType']:
                            description = interaction['interactionPair'][0]['description']
                            st.write(f"- {description}")
                else:
                    st.success("✅ Bilinen bir majör etkileşim bulunamadı.")
    else:
        st.warning("Lütfen her iki kutuyu da doldurun.")
