import streamlit as st
import pandas as pd
import pdfplumber
import re

st.title("Comparador de Comisión vs Contrato")

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


pdf_file = st.file_uploader("Subir contrato PDF", type=["pdf"])

tarifa_contrato = None

if pdf_file:

    tarifa_contrato = extraer_tarifa(pdf_file)

    if tarifa_contrato:
        st.success(f"Tarifa detectada en contrato: {tarifa_contrato}%")
    else:
        st.warning("No se encontró tarifa en el contrato")


excel_file = st.file_uploader("Subir Excel de transacciones", type=["xlsx","csv"])

if excel_file:

    df = pd.read_excel(excel_file)

    df_pagos = df[df["TX_reference"].str.startswith("PY", na=False)]
    df_fees = df[df["TX_reference"].str.startswith("SF", na=False)]

    df_merge = df_fees.merge(
        df_pagos,
        left_on="SF_transaction_related_id",
        right_on="TX_transaction_id",
        suffixes=("_fee","_pago")
    )

    df_merge["fee"] = abs(df_merge["TX_amount_fee"])
    df_merge["monto"] = df_merge["TX_amount_pago"]

    df_merge["porcentaje_fee"] = (df_merge["fee"] / df_merge["monto"]) * 100

    comision_promedio = df_merge["porcentaje_fee"].mean()

    st.write("Comisión promedio cobrada:", round(comision_promedio,2), "%")

    if tarifa_contrato:

        diferencia = abs(comision_promedio - tarifa_contrato)

        if diferencia < 0.1:
            st.success("La comisión coincide con el contrato")
        else:
            st.error("La comisión NO coincide con el contrato")

    st.dataframe(df_merge[["TX_reference_pago","monto","fee","porcentaje_fee"]])
