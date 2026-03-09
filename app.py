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
    
    d = {k: "0.00" for k in ["ORIGEN", "DESTINO", "ADUANA_SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]}

    if not texto.strip():
        return list(d.values())

    # --- LÓGICA DE EXTRACCIÓN UNIVERSAL ---

    # 1. EXPORTADOR DINÁMICO (Toma el nombre de cualquier empresa remitente)
    # Busca la etiqueta 'Remitente' (campo 33 o 1) y captura la línea de texto inmediata
    exp_match = re.search(r'(?:33\s*Remitente|1\s*Nombre\s*y\s*domicilio\s*del\s*remitente)[^\n]*\n\s*([A-Z0-9\s.]{3,})', texto, re.IGNORECASE)
    if exp_match: d["EXPORTADOR"] = exp_match.group(1).strip()

    # 2. IMPORTADOR DINÁMICO (Campo 34 o 4)
    imp_match = re.search(r'(?:34\s*Destinatario|4\s*Nombre\s*y\s*domicilio\s*del\s*destinatario)[^\n]*\n\s*([A-Z0-9\s.]{3,})', texto, re.IGNORECASE)
    if imp_match: d["IMPORTADOR"] = imp_match.group(1).strip()

    # 3. DESTINO (Busca el patrón CIUDAD-PAIS saltando códigos aduaneros)
    # Busca 'destino final' y captura el texto en mayúsculas con guion (ej: ITAJAI-BRASIL)
    destino_match = re.search(r'8\s*Ciudad\s*y\s*pais\s*de\s*destino\s*final.*?([A-Z]{3,}\s*-\s*[A-Z]{3,})', texto, re.DOTALL | re.IGNORECASE)
    if destino_match:
        d["DESTINO"] = destino_match.group(1).strip()

    # 4. PATENTES (Tractor y Carreta/Semiremolque)
    # Busca patrones Mercosur (3 letras, 1 nro, 1 letra, 2 nros)
    patentes = re.findall(r'[A-Z]{3}\d[A-Z]\d{2}', texto)
    if len(patentes) >= 2:
        d["TRACTOR"] = patentes[0]
        d["CARRETA"] = patentes[1] # MKY4A91 detectado como segunda patente
    elif len(patentes) == 1:
        d["TRACTOR"] = patentes[0]

    # 5. FLETE (Extrae el monto destinatario de la tabla de gastos)
    flete_search = re.search(r'Flete.*?([\d]{3,}\.[\d]{2})', texto, re.DOTALL | re.IGNORECASE)
    if flete_search: d["FLETE"] = flete_search.group(1)

    # 6. SEGURO (Valor numérico debajo del flete)
    seguro_search = re.search(r'Seguro.*?([\d]+\.[\d]{2})', texto, re.DOTALL | re.IGNORECASE)
    if seguro_search: d["SEGURO"] = seguro_search.group(1)

    # 7. FECHA (DD-MM-AAAA)
    fecha_match = re.search(r'(\d{2}-\d{2}-\d{4})', texto)
    if fecha_match: d["FECHA"] = fecha_match.group(1)

    # 8. MIC Y CRT (Limpieza del prefijo 038)
    mic = re.search(r'26AR[A-Z0-9]+', texto)
    if mic: d["MIC"] = mic.group()
    crt = re.search(r'038AR[\d\.]+', texto)
    if crt: d["CRT"] = crt.group().replace("038", "", 1)

    # 9. VALOR, CHOFER, DNI Y FACTURA
    valor_match = re.search(r'(?:14|27)\s*Valor.*?\n\s*([\d.]+)', texto, re.DOTALL | re.IGNORECASE)
    if valor_match: d["VALOR"] = valor_match.group(1)
    chofer = re.search(r'CONDUCTOR\s*1?:\s*([^:]+)\s*DOC:', texto, re.IGNORECASE)
    if chofer: d["CHOFER"] = chofer.group(1).strip()
    dni = re.search(r'DOC:\s*([A-Z0-9\s.]+)', texto)
    if dni: d["DNI"] = dni.group(1).strip()
    fac = re.search(r'EXPORTACION\s*NRO\s*([\w-]+)', texto, re.IGNORECASE)
    if fac: d["FACTURA"] = fac.group(1)

    # 10. CAMPOS FIJOS
    d["ADUANA_SALIDA"] = "MENDOZA"
    d["ORIGEN"] = "ARGENTINA" if "ARGENTINA" in texto.upper() else "BRASIL"

    return [d["ORIGEN"], d["DESTINO"], d["ADUANA_SALIDA"], d["EXPORTADOR"], 
            d["IMPORTADOR"], d["FECHA"], d["MIC"], d["CRT"], d["FACTURA"], 
            d["VALOR"], d["FLETE"], d["TRACTOR"], d["CARRETA"], d["CHOFER"], d["DNI"], d["SEGURO"]]

# --- INTERFAZ ---
st.set_page_config(page_title="Sanchez Transportes", layout="wide")
st.title("🚚 Registro de Camiones - Sánchez Transportes")

archivo = st.file_uploader("Subir MIC/CRT (PDF)", type="pdf")

if archivo:
    with st.spinner('Analizando documento...'):
        fila = extraer_datos_profesional(archivo)
        columnas = ["ORIGEN", "DESTINO", "ADUANA SALIDA", "EXPORTADOR", "IMPORTADOR", "FECHA", "MIC", "CRT", "FACTURA", "VALOR", "FLETE", "TRACTOR", "CARRETA", "CHOFER", "DNI", "SEGURO"]
        
        st.write("### Datos detectados:")
        st.table(pd.DataFrame([fila], columns=columnas))
        
        if st.button("Confirmar y Guardar en Google Sheets"):
            if agregar_a_google_sheets(fila):
                st.success("✅ ¡Registro exitoso!")
        st.table(pd.DataFrame([fila], columns=columnas))
