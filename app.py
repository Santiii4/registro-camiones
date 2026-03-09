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
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"
    
    # Diccionario con los 17 campos requeridos para Sanchez Transportes
    d = {k: "0.00" for k in ["ORIGEN", "ADUANA", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # 1. EXPORTADOR (Solo la primera línea del remitente)
    exp_match = re.search(r'(?:33\s*Remitente|1\s*Nombre\s*y\s*domicilio\s*del\s*remitente)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if exp_match: d["EXPORTADOR"] = exp_match.group(1).strip() # Solo SIMPLOT ARGENTINA S R L

    # 2. IMPORTADOR (Solo la primera línea del destinatario)
    imp_match = re.search(r'(?:34\s*Destinatario|4\s*Nombre\s*y\s*domicilio\s*del\s*destinatario)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if imp_match: d["IMPORTADOR"] = imp_match.group(1).strip()

    # 3. DESTINO (Ciudad y pais de destino final)
    # Basado en Campo 8
    destino_match = re.search(r'8\s*Ciudad\s*y\s*pais\s*de\s*destino\s*final[^\n]*\n\s*([A-Z\s-]+)', texto, re.IGNORECASE)
    if destino_match: d["DESTINO"] = destino_match.group(1).split('\n')[0].strip() # ITAJAI-BRASIL

    # 4. FLETE (Monto Destinatario o Remitente)
    # Captura el 3200.00 de la tabla de gastos
    flete_monto = re.search(r'Flete[^\n]*?([\d]{3,}\.[\d]{2})', texto, re.IGNORECASE)
    if flete_monto: d["FLETE"] = flete_monto.group(1)

    # 5. CARRETA (Placa del Semiremolque)
    # Captura MKY4A91 del Campo 15
    patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto)
    if len(patentes) >= 2:
        d["TRACTOR"] = patentes[0]
        d["CARRETA"] = patentes[1] # Semiremolque
    elif len(patentes) == 1:
        d["TRACTOR"] = patentes[0]

    # 6. FECHA (DD-MM-AAAA)
    fecha_match = re.search(r'7\s*Lugar,?\s*pais\s*y\s*fecha.*?\n.*?([\d]{2}-[\d]{2}-[\d]{4})', texto, re.DOTALL | re.IGNORECASE)
    if fecha_match: d["FECHA"] = fecha_match.group(1)

    # 7. MIC Y CRT (Limpieza de CRT)
    mic = re.search(r'26AR[A-Z0-9]+', texto)
    if mic: d["MIC"] = mic.group()
    crt = re.search(r'038AR[\d\.]+', texto)
    if crt: d["CRT"] = crt.group().replace("038", "", 1)

    # Campos Fijos y Otros
    d["ADUANA_SALIDA"] = "MENDOZA"
    d["ORIGEN"] = "ARGENTINA" if "ARGENTINA" in texto.upper() else "BRASIL"
    d["ADUANA"] = "MENDOZA-ARGENTINA" # Aduana de partida campo 7

    return [d["ORIGEN"], d["ADUANA"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], 
            d["IMPORTADOR"], d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], 
            d["VALOR"], d["FLETE"], d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Procesando datos del transporte...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Vista previa de datos detectados:")
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Guardar en Planilla Drive"):
            if agregar_a_google_sheets(fila):
                st.success("✅ Registro completado exitosamente.")