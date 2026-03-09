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
        
        # Función de búsqueda "inteligente" (no importa si hay mayúsculas o minúsculas)
        def buscar(patron, texto_fuente, default=""):
            match = re.search(patron, texto_fuente, re.S | re.I)
            return match.group(1).strip() if match else default

        # --- LÓGICA DE ORIGEN ---
        aduana = buscar(r"7 Aduana.*?partida\s*\n(.*?)\n", texto, "MENDOZA-ARGENTINA")
        origen_pais = "ARGENTINA" if "ARG" in aduana.upper() else ("BRASIL" if "BRA" in aduana.upper() else "PARAGUAY")

        # --- LIMPIEZA DE CRT (Sacar el 038 inicial) ---
        crt_raw = buscar(r"23 N.*?porte\s*(\d+)", texto)
        crt_limpio = crt_raw[3:] if crt_raw.startswith("038") else crt_raw

        # --- EXTRACCIÓN MEJORADA ---
        datos = [
            origen_pais,                                  
            aduana,                                       
            buscar(r"8 Ciudad.*?destino final\s*\n(.*?)\n", texto, "NOVO HAMBURGO-BRASIL"), 
            "MENDOZA",                                    
            buscar(r"33 Remitente\s*\n(.*?)\n", texto),    # EXPORTADOR
            buscar(r"34 Destinatario\s*\n(.*?)\n", texto), # IMPORTADOR
            buscar(r"F\. Ofic:\s*([\d-]+)", texto),       
            buscar(r"(26AR\w+)", texto),                  # MIC ELEC.
            crt_limpio,                                   # CRT
            
            # FACTURA: Busca después de "exportacion nro" o "FACTURA"
            buscar(r"(?:exportacion nro\.|FACTURA NRO:)\s*([\w-]+)", texto),
            
            buscar(r"27 Valor FOT\s*([\d.]+)", texto),   
            buscar(r"28 Fiete en USS\s*([\d.]+)", texto),
            
            # VEHÍCULOS: Tractor y Carreta
            buscar(r"11 Placa de Camion\s*(\w+)", texto),
            buscar(r"(?:Semiremolque|Reboque).*?Placa:\s*(\w+)", texto),
            
            buscar(r"CONDUCTOR 1:\s*([A-Z\s]+)", texto), 
            
            # DNI: Busca específicamente en el campo 40 tras "CI" o "DNI"
            buscar(r"40.*?CI\s*([\d.-]+)", texto),       
            
            buscar(r"29 Seguro en USS\s*([\d.]+)", texto)
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