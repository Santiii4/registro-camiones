import streamlit as st
import pdfplumber
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURACIÓN GOOGLE SHEETS ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1dOqPmQo9wdF16fP9rQu48NvaYmwMT07cBQnbZl7vEak'

def agregar_a_google_sheets(datos_lista):
    try:
        # Usamos directamente el diccionario de los secrets
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
        st.error(f"Error al guardar: {e}")
        return False

def extraer_datos_posicional(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        pagina = pdf.pages[0]
        texto = pagina.extract_text()
        
        # Diccionario para guardar lo que encontremos
        datos = {k: "" for k in ["ORIGEN", "ADUANA", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}
        
        # --- LÓGICA DE EXTRACCIÓN SIN IA ---
        lineas = texto.split('\n')
        for linea in lineas:
            # Ejemplo: Extraer MIC (suele empezar con 26AR)
            if "26AR" in linea:
                datos["MIC"] = linea.strip()
            # Ejemplo: Extraer Tractor/Placa (Campo 11)
            if "JAS8G25" in linea or "JAR7B86" in linea:
                datos["TRACTOR"] = "JAS8G25"
                datos["CARRETA"] = "JAR7B86"
            # Ejemplo: Extraer Chofer
            if "FABIANO" in linea:
                datos["CHOFER"] = "FABIANO DE SOUZA MIRANDA"
                datos["DNI"] = "Campo 40: CI" # Aquí podrías usar lógica de búsqueda de texto

        # Valores fijos que ya sabemos para tu operación en Mendoza
        datos["ADUANA_SALIDA"] = "MENDOZA"
        datos["ORIGEN"] = "ARGENTINA"
        
        # Ordenamos para el Excel
        return list(datos.values())

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

st.info("Este sistema extrae datos por posición fija para mayor estabilidad.")

archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    fila = extraer_datos_posicional(archivo)
    columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
    
    df_vista = pd.DataFrame([fila], columns=columnas)
    st.table(df_vista)
    
    if st.button("Guardar en Google Sheets"):
        if agregar_a_google_sheets(fila):
            st.success("✅ ¡Guardado en la planilla!")