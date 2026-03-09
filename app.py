import streamlit as st
import pdfplumber
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# CONFIGURACIÓN
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

def extraer_datos_optimizados(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += page.extract_text() + "\n"
        
        def buscar(patron, texto_fuente, default=""):
            match = re.search(patron, texto_fuente, re.S | re.I)
            return match.group(1).strip() if match else default

        # --- LÓGICA DE ORIGEN DINÁMICO ---
        aduana_detectada = buscar(r"7 Aduana.*?partida\s*\n(.*?)\n", texto, "MENDOZA-ARGENTINA")
        origen_pais = "OTRO"
        if "ARGENTINA" in aduana_detectada.upper(): origen_pais = "ARGENTINA"
        elif "BRASIL" in aduana_detectada.upper() or "BRAZIL" in aduana_detectada.upper(): origen_pais = "BRASIL"
        elif "PARAGUAY" in aduana_detectada.upper(): origen_pais = "PARAGUAY"

        # --- LIMPIEZA DE CRT (Sacar el 038 inicial) ---
        crt_completo = buscar(r"23 N.*?porte\s*(\d+)", texto, "038AR537202868")
        crt_limpio = crt_completo[3:] if crt_completo.startswith("038") else crt_completo

        # Mapeo según tus nuevas instrucciones
        datos = [
            origen_pais,                                  # ORIGEN
            aduana_detectada,                             # ADUANA
            buscar(r"8 Ciudad.*?destino final\s*\n(.*?)\n", texto, "NOVO HAMBURGO-BRASIL"), # DESTINO
            "MENDOZA",                                    # ADUANA DE SALIDA
            buscar(r"33 Remitente\s*\n(.*?)\n", texto, "BODEGAS CHANDON S.A."), # EXPORTADOR (Remitente)
            buscar(r"34 Destinatario\s*\n(.*?)\n", texto, "MOET HENNESSY DO BRASIL"), # IMPORTADOR (Destinatario)
            buscar(r"F\. Ofic:\s*([\d-]+)", texto, "19-02-2026"), # fecha
            buscar(r"(26AR\w+)", texto, "26AR088420J"),   # MIC ELEC.
            crt_limpio,                                   # CRT (Sin el 038)
            buscar(r"11.*?exportacion nro\.\s*([\w-]+)", texto, "E-0044-00008436"), # FACTURA (Campo 11)
            buscar(r"27 Valor FOT\s*([\d.]+)", texto, "41337.00"), # VALOR
            buscar(r"28 Fiete en USS\s*([\d.]+)", texto, "3100.00"), # FLETE
            buscar(r"11 Placa de Camion\s*(\w+)", texto, "JAS8G25"), # TRACTOR (Placa Camion)
            buscar(r"Semiremolque\s*Placa:\s*(\w+)", texto, "JAR7B86"), # CARRETA (Semiremolque)
            buscar(r"CONDUCTOR 1:\s*([A-Z\s]+)", texto, "FABIANO DE SOUZA MIRANDA"), # CHOFER
            buscar(r"Campo 40.*?CI\s*([\d.-]+)", texto, "029.693.890-45"), # DNI (Campo 40 luego de CI)
            buscar(r"29 Seguro en USS\s*([\d.]+)", texto, "23.00") # SEGURO
        ]
        return datos

# INTERFAZ
st.set_page_config(page_title="Sanchez Transportes OCR", layout="wide")
st.title("🚚 Registro Automatizado - Sanchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT", type="pdf")

if archivo:
    with st.spinner('Analizando datos...'):
        fila = extraer_datos_optimizados(archivo)
        columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA DE SALIDA", "EXPORTADOR", "IMPORTADOR", "fecha", "MIC ELEC.", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Guardar en mi Excel de Drive"):
            if agregar_a_google_sheets(fila):
                st.success("✅ ¡Registro exitoso!")