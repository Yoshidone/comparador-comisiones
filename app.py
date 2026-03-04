import streamlit as st
import pandas as pd
import pdfplumber
import zipfile
import re
import pytesseract
from pdf2image import convert_from_bytes

st.title("Comparador de Comisiones por Contrato")

# -----------------------------
# Detectar comercio desde PDF
# -----------------------------

def detectar_comercio(pdf_file):

    nombre_archivo = pdf_file.name.lower()

    nombre_archivo = nombre_archivo.replace(".pdf","")
    nombre_archivo = nombre_archivo.replace("contrato","")
    nombre_archivo = nombre_archivo.replace("_"," ")
    nombre_archivo = nombre_archivo.replace("-"," ")

    return nombre_archivo.strip()


# -----------------------------
# Extraer tarifa desde PDF
# -----------------------------

def extraer_tarifa(pdf_file):

    texto = ""

    # intentar leer texto normal
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for pagina in pdf.pages:
                contenido = pagina.extract_text()
                if contenido:
                    texto += contenido
    except:
        pass

    # si no encontró texto usar OCR
    if texto.strip() == "":

        images = convert_from_bytes(pdf_file.read())

        for img in images:
            texto += pytesseract.image_to_string(img)

    patron = r'(\d+(\.\d+)?%)'
    resultado = re.search(patron, texto)

    if resultado:
        tarifa = resultado.group().replace("%","")
        return float(tarifa)

    return None


# -----------------------------
# Cargar archivo transacciones
# -----------------------------

def cargar_archivo(archivo):

    nombre = archivo.name.lower()

    if nombre.endswith(".zip"):

        with zipfile.ZipFile(archivo) as z:

            nombre_csv = z.namelist()[0]

            with z.open(nombre_csv) as f:
                df = pd.read_csv(f)

    elif nombre.endswith(".csv"):

        df = pd.read_csv(archivo)

    elif nombre.endswith(".xlsx"):

        df = pd.read_excel(archivo)

    else:

        st.error("Formato no soportado")
        return None

    return df


# -----------------------------
# Subir contrato
# -----------------------------

pdf_file = st.file_uploader("Subir contrato PDF", type=["pdf"])

tarifa_contrato = None
comercio = None

if pdf_file:

    comercio = detectar_comercio(pdf_file)

    st.success(f"Comercio detectado: {comercio}")

    tarifa_contrato = extraer_tarifa(pdf_file)

    if tarifa_contrato:

        st.success(f"Tarifa detectada en contrato: {tarifa_contrato}%")

    else:

        st.warning("No se detectó tarifa en el contrato")


# -----------------------------
# Subir archivo de transacciones
# -----------------------------

archivo = st.file_uploader(
    "Subir archivo de transacciones",
    type=["zip","csv","xlsx"]
)

if archivo and comercio:

    df = cargar_archivo(archivo)

    if df is not None:

        st.write("Archivo cargado correctamente")

        # normalizar nombre comercio
        df["Com_Nom"] = df["Com_Nom"].astype(str).str.lower()

        # filtrar comercio
        df = df[df["Com_Nom"].str.contains(comercio)]

        st.write("Transacciones encontradas:", len(df))

        if len(df) == 0:

            st.warning("No se encontraron transacciones para este comercio")

        else:

            # separar pagos y comisiones
            df_pagos = df[df["TX_reference"].astype(str).str.startswith("PY", na=False)]
            df_fees = df[df["TX_reference"].astype(str).str.startswith("SF", na=False)]

            # agrupar pagos por transacción
            pagos = df_pagos.groupby("TX_transaction_id")["TX_amount"].sum().reset_index()

            # agrupar fees por transacción
            fees = df_fees.groupby("TX_transaction_id")["OP_amount"].sum().reset_index()

            # unir pagos con fees
            df_merge = pagos.merge(fees, on="TX_transaction_id")

            # calcular comisión
            df_merge["fee"] = abs(df_merge["OP_amount"])
            df_merge["monto"] = df_merge["TX_amount"]

            df_merge["porcentaje_fee"] = (df_merge["fee"] / df_merge["monto"]) * 100

            comision_promedio = df_merge["porcentaje_fee"].mean()

            st.subheader("Resultado")

            st.write("Comisión promedio cobrada:", round(comision_promedio,2), "%")

            if tarifa_contrato:

                diferencia = abs(comision_promedio - tarifa_contrato)

                if diferencia < 0.1:

                    st.success("La comisión coincide con el contrato")

                else:

                    st.error("La comisión NO coincide con el contrato")

            st.dataframe(
                df_merge[
                    [
                        "TX_transaction_id",
                        "monto",
                        "fee",
                        "porcentaje_fee"
                    ]
                ]
            )
