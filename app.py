import streamlit as st
import pandas as pd
import pdfplumber
import zipfile
import re
from io import BytesIO

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

    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            contenido = pagina.extract_text()
            if contenido:
                texto += contenido

    patron = r'(\d+(\.\d+)?%)'
    resultado = re.search(patron, texto)

    if resultado:
        tarifa = resultado.group().replace("%","")
        return float(tarifa)

    return None


# -----------------------------
# SUBIR CONTRATO
# -----------------------------

pdf_file = st.file_uploader("Subir contrato PDF", type=["pdf"])

tarifa_contrato = None
comercio = None

if pdf_file:

    comercio = detectar_comercio(pdf_file)
    tarifa_contrato = extraer_tarifa(pdf_file)

    st.success(f"Comercio detectado: {comercio}")

    if tarifa_contrato:
        st.success(f"Tarifa contrato: {tarifa_contrato}%")
    else:
        st.warning("No se detectó tarifa en el contrato")


# -----------------------------
# SUBIR CSV COMPRIMIDO
# -----------------------------

archivo_zip = st.file_uploader("Subir CSV comprimido (.zip)", type=["zip"])

if archivo_zip and comercio:

    with zipfile.ZipFile(archivo_zip) as z:

        nombre_csv = z.namelist()[0]

        with z.open(nombre_csv) as f:
            df = pd.read_csv(f)

    st.write("Archivo cargado correctamente")

    # normalizar nombres
    df["Com_Nombre"] = df["Com_Nombre"].astype(str).str.lower()

    # filtrar comercio del contrato
    df = df[df["Com_Nombre"].str.contains(comercio)]

    st.write("Transacciones encontradas:", len(df))

    if len(df) == 0:
        st.warning("No se encontraron transacciones para ese comercio")

    else:

        # separar pagos y fees
        df_pagos = df[df["TX_reference"].astype(str).str.startswith("PY", na=False)]
        df_fees = df[df["TX_reference"].astype(str).str.startswith("SF", na=False)]

        # cruzar pagos con fee
        df_merge = df_fees.merge(
            df_pagos,
            left_on="SF_transaction_related_id",
            right_on="TX_transaction_id",
            suffixes=("_fee","_pago")
        )

        # calcular comisión
        df_merge["fee"] = abs(df_merge["TX_amount_fee"])
        df_merge["monto"] = df_merge["TX_amount_pago"]

        df_merge["porcentaje_fee"] = (df_merge["fee"] / df_merge["monto"]) * 100

        comision_promedio = df_merge["porcentaje_fee"].mean()

        st.subheader("Resultado")

        st.write(f"Comisión promedio cobrada: {round(comision_promedio,2)} %")

        if tarifa_contrato:

            diferencia = abs(comision_promedio - tarifa_contrato)

            if diferencia < 0.1:
                st.success("La comisión coincide con el contrato")
            else:
                st.error("La comisión NO coincide con el contrato")

        st.dataframe(
            df_merge[["TX_reference_pago","monto","fee","porcentaje_fee"]]
        )
