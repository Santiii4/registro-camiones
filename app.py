import streamlit as st
import pdfplumber
import pandas as pd
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURACIÓN GOOGLE SHEETS ---
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
        st.error(f"Error al guardar en la planilla: {e}")
        return False

def extraer_datos_profesional(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        texto = ""
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"
    
    # Diccionario con todos los campos requeridos para Mendoza
    d = {k: "No encontrado" for k in ["ORIGEN", "ADUANA", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # --- LÓGICA DE EXTRACCIÓN POR PATRONES ---
    
    # MIC y CRT (Basado en los estándares 26AR y 038AR) [cite: 8, 76]
    mic = re.search(r'26AR[A-Z0-9]+', texto)
    if mic: d["MIC"] = mic.group()

    crt = re.search(r'038AR[\d\.]+', texto)
    if crt: d["CRT"] = crt.group().replace("038", "", 1)

    # Aduanas y Países [cite: 23, 31, 86]
    if "ARGENTINA" in texto: d["ORIGEN"] = "ARGENTINA"
    
    aduana_partida = re.search(r'partida\s*\n*\s*([A-Z\s-]+)', texto, re.IGNORECASE)
    if aduana_partida: d["ADUANA"] = aduana_partida.group(1).split('\n')[0].strip()

    destino = re.search(r'destino\s*final\s*\n*.*\n*\s*([A-Z\s-]+)', texto, re.IGNORECASE)
    if destino: d["DESTINO"] = destino.group(1).split('\n')[0].strip()

    # Empresas (Exportador/Importador) [cite: 103, 106]
    exp = re.search(r'33\s*Remitente\s*\n*\s*([A-Z\s.0-9]+)', texto)
    if exp: d["EXPORTADOR"] = exp.group(1).strip()

    imp = re.search(r'34\s*Destinatario\s*\n*\s*([A-Z\s.0-9]+)', texto)
    if imp: d["IMPORTADOR"] = imp.group(1).strip()

    # Patentes (Busca el formato Mercosur de 7 caracteres) [cite: 45, 83]
    patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto)
    if len(patentes) >= 1: d["TRACTOR"] = patentes[0]
    if len(patentes) >= 2: d["CARRETA"] = patentes[1]

    # Chofer y Documento [cite: 130]
    chofer = re.search(r'CONDUCTOR\s*1?:\s*([^:]+)\s*DOC:', texto, re.IGNORECASE)
    if chofer: d["CHOFER"] = chofer.group(1).strip()

    dni = re.search(r'DOC:\s*([A-Z0-9\s.]+)', texto)
    if dni: d["DNI"] = dni.group(1).strip()

    # Valores Económicos [cite: 80, 89, 97]
    flete = re.search(r'28\s*Flete\s*en\s*U\$S\s*\n*\s*([\d,.]+)', texto)
    if flete: d["FLETE"] = flete.group(1)

    valor_fot = re.search(r'27\s*Valor\s*FOT\s*\n*\s*([\d,.]+)', texto)
    if valor_fot: d["VALOR"] = valor_fot.group(1)

    seguro = re.search(r'29\s*Seguro\s*en\s*U\$S\s*\n*\s*([\d,.]+)', texto)
    if seguro: d["SEGURO"] = seguro.group(1)

    # Factura (Extraída del campo 11) [cite: 118]
    fac = re.search(r'EXPORTACION\s*NRO\s*([\w-]+)', texto, re.IGNORECASE)
    if fac: d["FACTURA"] = fac.group(1)

    # Fecha oficial [cite: 112]
    fecha = re.search(r'F\.\s*Ofic:\s*([\d/-]+)', texto)
    if fecha: d["FECHA"] = fecha.group(1)

    # Campo fijo
    d["ADUANA_SALIDA"] = "MENDOZA"

    return [d["ORIGEN"], d["ADUANA"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], 
            d["IMPORTADOR"], d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], 
            d["VALOR"], d["FLETE"], d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Sistema de Registro - Sánchez Transportes")

st.markdown("""
### Instrucciones:
1. Sube el archivo **PDF** del MIC o CRT.
2. Verifica los datos en la tabla.
3. Haz clic en **Guardar** para enviarlos a tu planilla de Google Drive.
""")

archivo = st.file_uploader("Seleccionar archivo MIC/CRT", type="pdf")

if archivo:
    with st.spinner('Procesando documento...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Datos detectados:")
        df_vista = pd.DataFrame([fila], columns=columnas)
        st.table(df_vista)
        
        if st.button("Guardar en Google Sheets"):
            if agregar_a_google_sheets(fila):
                st.success("✅ Datos registrados correctamente en Mendoza.")