import streamlit as st
import pdfplumber
import pandas as pd
import google.generativeai as genai
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURACIÓN IA ---
# Es vital que 'gemini_api_key' esté en Settings > Secrets de Streamlit
genai.configure(api_key=st.secrets["gemini_api_key"])

# Modelo estable para 2026
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
        
        # Agrega la fila al final de la Hoja 1
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja 1!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
        return False

def extraer_con_ia(texto_pdf):
    # Forzamos respuesta JSON para evitar errores de formato
    generation_config = {
        "temperature": 0.1,
        "response_mime_type": "application/json",
    }
    
    prompt = f"""
    Actúa como un experto en logística de transporte para Sánchez Transportes. 
    Analiza este texto de un MIC/DTA o CRT y devuelve un JSON con estos campos exactos:
    - ORIGEN: 'ARGENTINA', 'BRASIL' o 'PARAGUAY' (según aduana de partida campo 7).
    - ADUANA: Nombre aduana campo 7.
    - DESTINO: Ciudad y país campo 8.
    - ADUANA_SALIDA: 'MENDOZA'.
    - EXPORTADOR: Nombre remitente campo 33.
    - IMPORTADOR: Nombre destinatario campo 34.
    - FECHA: Fecha oficial.
    - MIC_ELEC: Número que inicia con 26AR.
    - CRT: Número campo 23 (SIN el 038 inicial).
    - FACTURA: Número de factura campo 11 (tras 'exportacion nro').
    - VALOR: Campo 27.
    - FLETE: Campo 28.
    - TRACTOR: Placa camión campo 11.
    - CARRETA: Placa semiremolque.
    - CHOFER: Nombre conductor.
    - DNI: Campo 40 (tras CI o DNI).
    - SEGURO: Campo 29.

    Texto del PDF:
    {texto_pdf}
    """
    
    response = model_ia.generate_content(prompt, generation_config=generation_config)
    return json.loads(response.text)

def extraer_datos_ia(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"
    
    if not texto.strip():
        raise ValueError("No se pudo extraer texto del PDF. ¿Es una imagen?")
        
    res_json = extraer_con_ia(texto)
    
    # Mapeo ordenado para las columnas del Excel
    orden = [
        res_json.get("ORIGEN"), res_json.get("ADUANA"), res_json.get("DESTINO"), 
        res_json.get("ADUANA_SALIDA"), res_json.get("EXPORTADOR"), res_json.get("IMPORTADOR"), 
        res_json.get("FECHA"), res_json.get("MIC_ELEC"), res_json.get("CRT"), 
        res_json.get("FACTURA"), res_json.get("VALOR"), res_json.get("FLETE"), 
        res_json.get("TRACTOR"), res_json.get("CARRETA"), res_json.get("CHOFER"), 
        res_json.get("DNI"), res_json.get("SEGURO")
    ]
    return orden

# INTERFAZ DE USUARIO
st.set_page_config(page_title="Sanchez Transportes IA", layout="wide")
st.title("🚚 Registro Inteligente - Sanchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Analizando con Inteligencia Artificial...'):
        try:
            fila = extraer_datos_ia(archivo)
            columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA DE SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC ELEC.", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
            
            st.write("### Vista previa de datos detectados:")
            st.table(pd.DataFrame([fila], columns=columnas))
            
            if st.button("Confirmar y Guardar en Google Sheets"):
                if agregar_a_google_sheets(fila):
                    st.success("✅ ¡Datos guardados exitosamente!")
        except Exception as e:
            st.error(f"Error técnico: {e}")