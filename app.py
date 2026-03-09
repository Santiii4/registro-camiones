import streamlit as st
import pdfplumber
import pandas as pd
import google.generativeai as genai
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# CONFIGURACIÓN IA
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
        st.error(f"Error de conexión: {e}")
        return False

def extraer_con_ia(texto_pdf):
    prompt = f"""
    Actúa como un experto en logística de transporte. Analiza el texto de este MIC/DTA o CRT y devuelve un JSON puro con estos campos:
    - ORIGEN: Solo 'ARGENTINA', 'BRASIL' o 'PARAGUAY' (basado en el país de la aduana de partida campo 7).
    - ADUANA: Nombre de la aduana campo 7.
    - DESTINO: Ciudad y país del campo 8.
    - ADUANA_SALIDA: Siempre 'MENDOZA'.
    - EXPORTADOR: Nombre del remitente campo 33.
    - IMPORTADOR: Nombre del destinatario campo 34.
    - FECHA: Fecha del campo 'F. Ofic' o similar.
    - MIC_ELEC: Número que inicia con 26AR.
    - CRT: Número del campo 23 (SIN el 038 inicial).
    - FACTURA: Número de factura del campo 11 (luego de 'exportacion nro').
    - VALOR: Valor FOT campo 27.
    - FLETE: Flete campo 28.
    - TRACTOR: Placa de camión campo 11.
    - CARRETA: Placa de semiremolque/reboque.
    - CHOFER: Nombre del conductor.
    - DNI: Documento en el campo 40 (luego de CI o DNI).
    - SEGURO: Valor del seguro campo 29.

    Texto: {texto_pdf}
    Responde UNICAMENTE el JSON.
    """
    response = model_ia.generate_content(prompt)
    limpio = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(limpio)

def extraer_datos_ia(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
    
    # Procesar con Inteligencia Artificial
    res_json = extraer_con_ia(texto)
    
    # Ordenamos la lista según tu planilla de 17 columnas
    orden = [
        res_json.get("ORIGEN"), res_json.get("ADUANA"), res_json.get("DESTINO"), 
        res_json.get("ADUANA_SALIDA"), res_json.get("EXPORTADOR"), res_json.get("IMPORTADOR"), 
        res_json.get("FECHA"), res_json.get("MIC_ELEC"), res_json.get("CRT"), 
        res_json.get("FACTURA"), res_json.get("VALOR"), res_json.get("FLETE"), 
        res_json.get("TRACTOR"), res_json.get("CARRETA"), res_json.get("CHOFER"), 
        res_json.get("DNI"), res_json.get("SEGURO")
    ]
    return orden

# INTERFAZ
st.set_page_config(page_title="Sanchez Transportes IA", layout="wide")
st.title("🚚 Registro Inteligente - Sanchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('La IA está analizando el documento...'):
        try:
            fila = extraer_datos_ia(archivo)
            columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA DE SALIDA", "EXPORTADOR", "IMPORTADOR", "fecha", "MIC ELEC.", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
            
            st.write("### Datos detectados por IA:")
            st.table(pd.DataFrame([fila], columns=columnas))
            
            if st.button("Guardar en mi Excel de Drive"):
                if agregar_a_google_sheets(fila):
                    st.success("✅ ¡Registro exitoso en la planilla!")
        except Exception as e:
            st.error(f"Error procesando el PDF con IA: {e}")