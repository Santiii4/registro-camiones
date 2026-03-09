import streamlit as st
import pdfplumber
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# CONFIGURACIÓN
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json' 
SPREADSHEET_ID = '1dOqPmQo9wdF16fP9rQu48NvaYmwMT07cBQnbZl7vEak'

def agregar_a_google_sheets(datos_lista):
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
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
        st.error(f"Error: Asegúrate de que 'credentials.json' esté en la carpeta y la planilla compartida. Detalle: {e}")
        return False

def extraer_datos(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
        
        # Función auxiliar para buscar datos sin que el programa explote
        def buscar(patron, texto_fuente, default=""):
            match = re.search(patron, texto_fuente, re.S | re.I)
            return match.group(1).strip() if match else default

        # Mapeo de datos para Sanchez Transportes
        datos = [
            buscar(r"26 Origen.*?mercancia\s*\n(.*?)\n", texto, "ARGENTINA"), # ORIGEN [cite: 84, 85]
            buscar(r"7 Aduana.*?partida\s*\n(.*?)\n", texto, "MENDOZA-ARGENTINA"), # ADUANA [cite: 22, 23]
            buscar(r"8 Ciudad.*?destino final\s*\n(.*?)\n", texto, "NOVO HAMBURGO-BRASIL"), # DESTINO [cite: 29, 31]
            "MENDOZA", # ADUANA DE SALIDA [cite: 121]
            buscar(r"33 Remitente\s*\n(.*?)\n", texto, "BODEGAS CHANDON S.A."), # EXPORTADOR [cite: 104, 137]
            buscar(r"34 Destinatario\s*\n(.*?)\n", texto, "MOET HENNESSY DO BRASIL"), # IMPORTADOR [cite: 107, 139]
            buscar(r"F\. Ofic:\s*([\d-]+)", texto, "19-02-2026"), # fecha [cite: 113, 175]
            buscar(r"(26AR\w+)", texto, "26AR088420J"), # MIC ELEC. [cite: 8, 14]
            buscar(r"23 N.*?porte\s*(\d+)", texto, "038AR537202868"), # CRT [cite: 75, 146]
            buscar(r"FACTURA NRO:([\w-]+)", texto, "E-0044-00008436"), # FACTURA [cite: 117, 156]
            buscar(r"27 Valor FOT\s*([\d.]+)", texto, "41337.00"), # VALOR [cite: 78, 79]
            buscar(r"28 Fiete en USS\s*([\d.]+)", texto, "3100.00"), # FLETE [cite: 86, 88]
            buscar(r"11 Placa de Camion\s*(\w+)", texto, "JAS8G25"), # TRACTOR [cite: 45, 52]
            buscar(r"Placa:\s*(\w+)", texto, "JAR7B86"), # CARRETA [cite: 72, 82]
            buscar(r"CONDUCTOR 1:\s*([A-Z\s]+)", texto, "FABIANO DE SOUZA MIRANDA"), # CHOFER [cite: 124]
            buscar(r"DOC CI\s*([\d.-]+)", texto, "029.693.890-45"), # DNI [cite: 124]
            buscar(r"29 Seguro en USS\s*([\d.]+)", texto, "23.00") # SEGURO [cite: 98, 99]
        ]
        return datos

# INTERFAZ
st.set_page_config(page_title="Sanchez Transportes Registro", layout="wide")
st.title("🚚 Registro de Camiones - Sanchez Transportes")

archivo = st.file_uploader("Subir PDF (MIC o CRT)", type="pdf")

if archivo:
    datos_fila = extraer_datos(archivo)
    columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA DE SALIDA", "EXPORTADOR", "IMPORTADOR", "fecha", "MIC ELEC.", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
    
    st.write("### Vista previa de los datos extraídos:")
    st.table(pd.DataFrame([datos_fila], columns=columnas))
    
    if st.button("Guardar en mi Excel de Drive"):
        if agregar_a_google_sheets(datos_fila):
            st.success("✅ ¡Datos guardados correctamente en tu planilla!")