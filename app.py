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
    
    # Valores por defecto
    d = {k: "No encontrado" for k in ["ORIGEN", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "SEMIREMOLQUE", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # --- CAMPOS INTACTOS ---
    d["ORIGEN"] = "ARGENTINA" if "ARGENTINA" in texto.upper() else "BRASIL"
    d["ADUANA_SALIDA"] = "MENDOZA"
    
    mic = re.search(r'26AR[A-Z0-9]+', texto)
    if mic: d["MIC"] = mic.group()
    
    crt = re.search(r'038AR[\d\.]+', texto)
    if crt: d["CRT"] = crt.group().replace("038", "", 1)
    
    chofer = re.search(r'CONDUCTOR\s*1?:\s*([^:]+)\s*DOC:', texto, re.IGNORECASE)
    if chofer: d["CHOFER"] = chofer.group(1).strip()
    
    dni = re.search(r'DOC:\s*([A-Z0-9\s.]+)', texto)
    if dni: d["DNI"] = dni.group(1).strip()

    patentes = re.findall(r'[A-Z]{3}\d[A-Z\d]\d{2}|[A-Z]{3}\d{4}', texto)
    if len(patentes) >= 1: d["TRACTOR"] = patentes[0]
    
    fac_match = re.search(r'FACTURA\s*NRO\s*:\s*([\w-]+)', texto, re.IGNORECASE)
    if fac_match: d["FACTURA"] = fac_match.group(1)

    valor_match = re.search(r'(?:14|27)\s*Valor.*?\n\s*([\d.]+)', texto, re.IGNORECASE)
    if valor_match: d["VALOR"] = valor_match.group(1)

    semi_match = re.search(r'Semiremolque.*?Placa:\s*([A-Z0-9]{6,7})', texto, re.DOTALL | re.IGNORECASE)
    if semi_match:
        d["SEMIREMOLQUE"] = semi_match.group(1)
    elif len(patentes) >= 2:
        d["SEMIREMOLQUE"] = patentes[1]

    fecha_match = re.search(r'7\s*Lugar.*?fecha.*?\d{2}-\d{2}-\d{4}', texto, re.DOTALL | re.IGNORECASE)
    if fecha_match:
        solo_fecha = re.search(r'(\d{2}-\d{2}-\d{4})', fecha_match.group(0))
        if solo_fecha: d["FECHA"] = solo_fecha.group(1)

    destino_match = re.search(r'8\s*Ciudad.*?destino\s*final[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if destino_match: 
        destino_limpio = re.split(r'\s{2,}', destino_match.group(1).strip())[0]
        destino_limpio = re.sub(r'\d+', '', destino_limpio)
        destino_limpio = re.sub(r'[^a-zA-Z\s\-]', '', destino_limpio)
        d["DESTINO"] = re.sub(r'\s{2,}', ' ', destino_limpio).strip()

    # --- CAMPOS CON CORRECCIÓN DE COLUMNAS ---

    # IMPORTADOR
    imp_match = re.search(r'(?:4\s*Nombre.*?destinatario|34\s*Destinatario)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if imp_match: 
        imp_texto = imp_match.group(1).strip()
        # NUEVO: Corta si encuentra la columna de al lado (separada por espacios múltiples)
        imp_texto = re.split(r'\s{2,}', imp_texto)[0]
        imp_texto = re.split(r'(?:\s+AV\.|\s+RST|\s+RUA|\s+C\.)', imp_texto, flags=re.IGNORECASE)[0]
        imp_texto = re.sub(r'\d+', '', imp_texto)
        imp_texto = re.sub(r'[^a-zA-Z\s\.\-]', '', imp_texto)
        d["IMPORTADOR"] = re.sub(r'\s{2,}', ' ', imp_texto).strip()

    # EXPORTADOR
    exp_match = re.search(r'(?:1\s*Nombre.*?remitente|33\s*Remitente)[^\n]*\n\s*([^\n]+)', texto, re.IGNORECASE)
    if exp_match: 
        exp_texto = exp_match.group(1).strip()
        # NUEVO: Corta si encuentra la columna de al lado (Aduana de destino, etc.)
        exp_texto = re.split(r'\s{2,}', exp_texto)[0]
        exp_texto = re.sub(r'038\s*N\s*A.*?NOVO HAMBURGO-', '', exp_texto, flags=re.IGNORECASE).strip()
        exp_texto = re.split(r'(?:\s+AV\.|\s+RST|\s+RUA|\s+C\.)', exp_texto, flags=re.IGNORECASE)[0]
        exp_texto = re.sub(r'\d+', '', exp_texto)
        exp_texto = re.sub(r'[^a-zA-Z\s\.\-]', '', exp_texto)
        d["EXPORTADOR"] = re.sub(r'\s{2,}', ' ', exp_texto).strip()

    # --- FLETE Y SEGURO (Intactos) ---
    texto_lineal = texto.replace('\n', ' ')

    flete_zona = re.search(r'Flete\s*/\s*Frete(.*?)(?:Seguro\s*/|Otros\s*/|TOTAL)', texto_lineal, re.IGNORECASE)
    if flete_zona:
        montos = re.findall(r'(\d*\.\d{2})', flete_zona.group(1))
        valores = [float(m) for m in montos if m != '.00']
        d["FLETE"] = f"{max(valores):.2f}" if valores else "0.00"
    else:
        d["FLETE"] = "0.00"

    seguro_zona = re.search(r'Seguro\s*/\s*Seguro(.*?)(?:Otros\s*/|TOTAL)', texto_lineal, re.IGNORECASE)
    if seguro_zona:
        montos = re.findall(r'(\d*\.\d{2})', seguro_zona.group(1))
        valores = [float(m) for m in montos if m != '.00']
        d["SEGURO"] = f"{max(valores):.2f}" if valores else "0.00"
    else:
        d["SEGURO"] = "0.00"

    return [d["ORIGEN"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], d["IMPORTADOR"], 
            d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], d["VALOR"], d["FLETE"], 
            d["TRACTOR"], d["SEMIREMOLQUE"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Procesando documento...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "SEMIREMOLQUE", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Vista previa:")
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Confirmar y Guardar en Google Sheets"):
            if agregar_a_google_sheets(fila):
                st.success("✅ ¡Registro completado!")
