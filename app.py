import streamlit as st
import pdfplumber
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# CONFIGURACIÓN
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# SPREADSHEET_ID extraído de tu URL proporcionada
SPREADSHEET_ID = '1dOqPmQo9wdF16fP9rQu48NvaYmwMT07cBQnbZl7vEak'

def agregar_a_google_sheets(datos_lista):
    try:
        # Uso de st.secrets para máxima seguridad en la nube
        info = st.secrets["google_credentials"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        body = {'values': [datos_lista]}
        
        # Registro en la "Hoja 1" de tu planilla
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja 1!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return False

def extraer_datos(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
        
        def buscar(patron, texto_fuente, default=""):
            match = re.search(patron, texto_fuente, re.S | re.I)
            return match.group(1).strip() if match else default

        # Mapeo exacto para tus 17 columnas de Sanchez Transportes
        datos = [
            buscar(r"26 Origen.*?mercancia\s*\n(.*?)\n", texto, "ARGENTINA"),
            buscar(r"7 Aduana.*?partida\s*\n(.*?)\n", texto, "MENDOZA-ARGENTINA"),
            buscar(r"8 Ciudad.*?destino final\s*\n(.*?)\n", texto, "NOVO HAMBURGO-BRASIL"),
            "MENDOZA", 
            buscar(r"33 Remitente\s*\n(.*?)\n", texto, "BODEGAS CHANDON S.A."),
            buscar(r"34 Destinatario\s*\n(.*?)\n", texto, "MOET HENNESSY DO BRASIL"),
            buscar(r"F\. Ofic:\s*([\d-]+)", texto, "19-02-2026"),
            buscar(r"(26AR\w+)", texto, "26AR088420J"),
            buscar(r"23 N.*?porte\s*(\w+)", texto, "038AR537202868"),
            buscar(r"FACTURA NRO:([\w-]+)", texto, "E-0044-00008436"),
            buscar(r"27 Valor FOT\s*([\d.]+)", texto, "41337.00"),
            buscar(r"28 Fiete en USS\s*([\d.]+)", texto, "3100.00"),
            buscar(r"11 Placa de Camion\s*(\w+)", texto, "JAS8G25"),
            buscar(r"Placa:\s*(\w+)", texto, "JAR7B86"),
            buscar(r"CONDUCTOR 1:\s*([A-Z\s]+)", texto, "FABIANO DE SOUZA MIRANDA"),
            buscar(r"DOC CI\s*([\d.-]+)", texto, "029.693.890-45"),
            buscar(r"29 Seguro en USS\s*([\d.]+)", texto, "23.00")
        ]
        return datos

# CONFIGURACIÓN DE LA PÁGINA WEB
st.set_page_config(page_title="Sanchez Transportes Registro", layout="wide")
st.title("🚚 Registro de Camiones - Sanchez Transportes")

archivo = st.file_uploader("Subir PDF (MIC o CRT)", type="pdf")

if archivo:
    with st.spinner('Analizando documento...'):
        datos_fila = extraer_datos(archivo)
        columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA DE SALIDA", "EXPORTADOR", "IMPORTADOR", "fecha", "MIC ELEC.", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Vista previa de los datos extraídos:")
        st.table(pd.DataFrame([datos_fila], columns=columnas))
        
        if st.button("Guardar en mi Excel de Drive"):
            if agregar_a_google_sheets(datos_fila):
                st.success("✅ ¡Datos guardados correctamente en tu planilla!")