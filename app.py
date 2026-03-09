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
        st.error(f"Error al guardar: {e}")
        return False

def extraer_datos_profesional(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            texto += (page.extract_text() or "") + "\n"
    
    d = {k: "No encontrado" for k in ["ORIGEN", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # 1. EXPORTADOR: Solo la primera línea tras 'Remitente'
    exp_match = re.search(r'(?:33\s*Remitente|1\s*Nombre)[^\n]*\n\s*([A-Z\s.]{3,})', texto, re.IGNORECASE)
    if exp_match: d["EXPORTADOR"] = exp_match.group(1).strip()

    # 2. FECHA: Busca el patrón DD-MM-AAAA en el campo 7
    fecha_match = re.search(r'7\s*Lugar.*?\n.*?([\d]{2}-[\d]{2}-[\d]{4})', texto, re.DOTALL)
    if fecha_match: d["FECHA"] = fecha_match.group(1)

    # 3. CRT: Busca 038AR y quita el 038 inicial
    crt_match = re.search(r'038AR[\d\.]+', texto)
    if crt_match: d["CRT"] = crt_match.group().replace("038", "", 1)

    # 4. FACTURA: Busca tras 'FACTURA EXPORTACION NRO'
    fac_match = re.search(r'EXPORTACION\s*NRO\s*([\w-]+)', texto, re.IGNORECASE)
    if fac_match: d["FACTURA"] = fac_match.group(1)

    # 5. TRACTOR Y CARRETA: Identifica patentes Mercosur
    patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto)
    if len(patentes) >= 2:
        d["TRACTOR"] = patentes[0]
        d["CARRETA"] = patentes[1] # Semiremolque
    elif len(patentes) == 1:
        d["TRACTOR"] = patentes[0]

    # 6. CHOFER Y DNI: Busca 'CONDUCTOR' y el documento tras 'DOC:'
    chofer_match = re.search(r'CONDUCTOR\s*1?:\s*([^:]+)\s*DOC:', texto, re.IGNORECASE)
    if chofer_match: d["CHOFER"] = chofer_match.group(1).strip()
    
    dni_match = re.search(r'DOC:\s*([A-Z0-9\s.]+)', texto)
    if dni_match: d["DNI"] = dni_match.group(1).strip()

    # 7. SEGURO Y FLETE: Busca montos decimales en la tabla de gastos
    flete_match = re.search(r'Flete.*?([\d]{3,}\.[\d]{2})', texto, re.DOTALL | re.IGNORECASE)
    if flete_match: d["FLETE"] = flete_match.group(1)
    
    seguro_match = re.search(r'Seguro.*?([\d]+\.[\d]{2})', texto, re.DOTALL | re.IGNORECASE)
    if seguro_match: d["SEGURO"] = seguro_match.group(1)

    # 8. DESTINO: Ciudad y país de destino final
    destino_match = re.search(r'destino\s*final.*?([A-Z\s]+-[A-Z\s]+)', texto, re.DOTALL | re.IGNORECASE)
    if destino_match: d["DESTINO"] = destino_match.group(1).strip()

    # Campos fijos
    d["ORIGEN"] = "ARGENTINA"
    d["ADUANA_SALIDA"] = "MENDOZA"
    mic_match = re.search(r'26AR[A-Z0-9]+', texto)
    if mic_match: d["MIC"] = mic_match.group()

    return [d["ORIGEN"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], d["IMPORTADOR"], 
            d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], d["VALOR"], d["FLETE"], 
            d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Analizando documento...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Guardar en Google Sheets"):
            if agregar_a_google_sheets(fila):
                st.success("✅ ¡Guardado!")
