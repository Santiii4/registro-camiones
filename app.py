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
    
    d = {k: "0.00" for k in ["ORIGEN", "ADUANA", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # 1. EXPORTADOR E IMPORTADOR (Solo la primera línea del nombre)
    exp_match = re.search(r'(?:33\s*Remitente|1\s*Nombre\s*y\s*domicilio\s*del\s*remitente)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if exp_match: d["EXPORTADOR"] = exp_match.group(1).strip()

    imp_match = re.search(r'(?:34\s*Destinatario|4\s*Nombre\s*y\s*domicilio\s*del\s*destinatario)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if imp_match: d["IMPORTADOR"] = imp_match.group(1).strip()

    # 2. FECHA (Campo 7: Lugar, país y fecha)
    fecha_match = re.search(r'7\s*Lugar,?\s*pais\s*y\s*fecha.*?\n.*?([\d]{2}-[\d]{2}-[\d]{4})', texto, re.DOTALL | re.IGNORECASE)
    if fecha_match: d["FECHA"] = fecha_match.group(1)

    # 3. FLETE Y SEGURO (Búsqueda en tabla de gastos)
    flete_monto = re.search(r'Flete[^\n]*?([\d]{3,}\.[\d]{2})', texto, re.IGNORECASE)
    if flete_monto: d["FLETE"] = flete_monto.group(1)

    # Seguro: busca un valor decimal (como .00 o 23.00) que esté cerca de la palabra Seguro
    seguro_monto = re.search(r'Seguro[^\n]*?([\d]*\.[\d]{2})', texto, re.IGNORECASE)
    if seguro_monto: d["SEGURO"] = seguro_monto.group(1)

    # 4. VALOR (Campo 14 o 27)
    valor_match = re.search(r'(?:14|27)\s*Valor[^\n]*\n\s*([\d.]+)', texto, re.IGNORECASE)
    if valor_match: d["VALOR"] = valor_match.group(1)

    # 5. PATENTES (Tractor y Carreta/Semiremolque)
    patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto)
    if len(patentes) >= 2:
        d["TRACTOR"] = patentes[0]
        d["CARRETA"] = patentes[1]
    elif len(patentes) == 1:
        d["TRACTOR"] = patentes[0]

    # 6. DESTINO (Campo 8: Ciudad y país de destino final)
    destino_match = re.search(r'8\s*Ciudad\s*y\s*pais\s*de\s*destino\s*final[^\n]*\n\s*([A-Z\s-]+)', texto, re.IGNORECASE)
    if destino_match: d["DESTINO"] = destino_match.group(1).split('\n')[0].strip()

    # 7. MIC Y CRT (Limpieza del 038)
    mic = re.search(r'26AR[A-Z0-9]+', texto)
    if mic: d["MIC"] = mic.group()
    crt = re.search(r'038AR[\d\.]+', texto)
    if crt: d["CRT"] = crt.group().replace("038", "", 1)

    # 8. CHOFER Y DNI
    chofer = re.search(r'CONDUCTOR\s*1?:\s*([^:]+)\s*DOC:', texto, re.IGNORECASE)
    if chofer: d["CHOFER"] = chofer.group(1).strip()
    dni = re.search(r'DOC:\s*([A-Z0-9\s.]+)', texto)
    if dni: d["DNI"] = dni.group(1).strip()

    # 9. FACTURA (Campo 11)
    fac = re.search(r'EXPORTACION\s*NRO\s*([\w-]+)', texto, re.IGNORECASE)
    if fac: d["FACTURA"] = fac.group(1)

    # Campos fijos
    d["ADUANA_SALIDA"] = "MENDOZA"
    d["ADUANA"] = "MENDOZA-ARGENTINA"
    d["ORIGEN"] = "ARGENTINA" if "ARGENTINA" in texto.upper() else "BRASIL"

    return [d["ORIGEN"], d["ADUANA"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], 
            d["IMPORTADOR"], d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], 
            d["VALOR"], d["FLETE"], d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Extrayendo información...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "ADUANA", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Datos detectados:")
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Guardar en Google Sheets"):
            if agregar_a_google_sheets(fila):
                st.success("✅ ¡Registro guardado exitosamente!")