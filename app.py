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
        st.error(f"Error de conexión con Sheets: {e}")
        return False

def extraer_datos_por_zona(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        # Usamos la primera página para el MIC y la segunda para el CRT si existe
        pagina = pdf.pages[0]
        texto_completo = pagina.extract_text()
        
        # Diccionario de resultados
        d = {k: "No detectado" for k in ["ORIGEN", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

        # --- LÓGICA DE RASTREO POR PALABRAS CLAVE ---
        
        # MIC: Siempre empieza con 26AR
        mic = re.search(r'26AR[A-Z0-9]+', texto_completo)
        if mic: d["MIC"] = mic.group()

        # CRT: Siempre empieza con 038AR, pero limpiamos el 038
        crt = re.search(r'038AR[\d\.]+', texto_completo)
        if crt: d["CRT"] = crt.group().replace("038", "", 1)

        # EXPORTADOR: Buscamos la línea justo debajo de 'Remitente'
        lineas = texto_completo.split('\n')
        for i, linea in enumerate(lineas):
            if "Remitente" in linea or "33" in linea[:3]:
                if i+1 < len(lineas): d["EXPORTADOR"] = lineas[i+1].strip()
            if "Destinatario" in linea or "34" in linea[:3]:
                if i+1 < len(lineas): d["IMPORTADOR"] = lineas[i+1].strip()
            if "destino final" in linea.lower():
                if i+1 < len(lineas): d["DESTINO"] = lineas[i+1].strip()

        # PATENTES: Buscamos el formato ABC1D23 (Mercosur)
        patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto_completo)
        if len(patentes) >= 1: d["TRACTOR"] = patentes[0]
        if len(patentes) >= 2: d["CARRETA"] = patentes[1]

        # COSTOS: Buscamos fletes y seguros (Formato 0000.00)
        montos = re.findall(r'\d{1,}\.\d{2}', texto_completo)
        if len(montos) >= 1: d["VALOR"] = montos[0]
        if len(montos) >= 2: d["FLETE"] = montos[1] # Usualmente el segundo monto grande es el flete

        # Campos fijos para Sanchez Transportes
        d["ADUANA_SALIDA"] = "MENDOZA"
        d["ORIGEN"] = "ARGENTINA"

        return [d["ORIGEN"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], d["IMPORTADOR"], 
                d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], d["VALOR"], d["FLETE"], 
                d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro Directo - Sánchez Transportes")

archivo = st.file_uploader("Subir PDF", type="pdf")

if archivo:
    fila = extraer_datos_por_zona(archivo)
    columnas = ["ORIGEN", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
    
    st.table(pd.DataFrame([fila], columns=columnas))
    
    if st.button("Guardar en Drive"):
        if agregar_a_google_sheets(fila):
            st.success("¡Datos guardados!")
