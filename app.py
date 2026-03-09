import streamlit as st
import pdfplumber
import pandas as pd
import google.generativeai as genai
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# CONFIGURACIÓN IA ESTABLE
genai.configure(api_key=st.secrets["gemini_api_key"])
model_ia = genai.GenerativeModel('gemini-1.5-flash')

# CONFIGURACIÓN GOOGLE SHEETS
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1dOqPmQo9wdF16fP9rQu48NvaYmwMT07cBQnbZl7vEak'

def agregar_a_google_sheets(datos_lista):
    try:
        info = st.secrets["google_credentials"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        body = {'values': [datos_lista]}
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja 1!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error de conexión con Sheets: {e}")
        return False

def extraer_con_ia(texto_pdf):
    # Forzamos JSON para evitar errores de lectura
    prompt = f"Analiza este MIC/CRT y devuelve JSON con campos: ORIGEN, ADUANA, DESTINO, ADUANA_SALIDA(MENDOZA), EXPORTADOR, IMPORTADOR, FECHA, MIC_ELEC(26AR...), CRT(sin 038), FACTURA(campo 11), VALOR(27), FLETE(28), TRACTOR(11), CARRETA, CHOFER, DNI(40), SEGURO(29). Texto: {texto_pdf}"
    
    response = model_ia.generate_content(
        prompt, 
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def extraer_datos_ia(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = "\n".join([page.extract_text() or "" for page in pdf.pages])
    
    res = extraer_con_ia(texto)
    return [res.get(k) for k in ["ORIGEN", "ADUANA", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC_ELEC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]]

# INTERFAZ
st.set_page_config(page_title="Sanchez Transportes IA", layout="wide")
st.title("🚚 Registro Inteligente - Sanchez Transportes")
archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Analizando...'):
        try:
            fila = extraer_datos_ia(archivo)
            st.table(pd.DataFrame([fila], columns=["ORIGEN", "ADUANA", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]))
            if st.button("Guardar en Drive"):
                if agregar_a_google_sheets(fila): st.success("¡Guardado!")
        except Exception as e:
            st.error(f"Error: {e}")