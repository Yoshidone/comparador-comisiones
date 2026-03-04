import streamlit as st
import pandas as pd
import zipfile

st.title("Comparador de Comisiones por Contrato")

# -----------------------------
# CONFIGURACIÓN DEL CONTRATO
# -----------------------------

st.subheader("Configuración del contrato")

texto_contrato = st.text_area(
    "Escribe las tarifas del contrato en formato: volumen_min-volumen_max | porcentaje | fija",
    """0-500000 | 2.30 | 0.90
500000-2000000 | 2.10 | 0.90
2000000-4000000 | 1.90 | 0.90
4000000-999999999 | 1.80 | 0.90"""
)

contrato = []

for linea in texto_contrato.split("\n"):

    if linea.strip() == "":
        continue

    partes = linea.split("|")

    volumen = partes[0].strip().split("-")

    volumen_min = float(volumen[0])
    volumen_max = float(volumen[1])

    comision_porcentaje = float(partes[1].strip())
    comision_fija = float(partes[2].strip())

    contrato.append({
        "Volumen_min": volumen_min,
        "Volumen_max": volumen_max,
        "Comision_%": comision_porcentaje,
        "Comision_fija": comision_fija
    })

contrato = pd.DataFrame(contrato)

st.write("Contrato interpretado:")
st.dataframe(contrato)

# -----------------------------
# COMERCIO
# -----------------------------

comercio = st.text_input(
    "Nombre del comercio (ej: pay retailers)"
).lower()

# -----------------------------
# FUNCIÓN CARGAR ARCHIVO
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
# SUBIR ARCHIVO
# -----------------------------

archivo = st.file_uploader(
    "Subir archivo de transacciones",
    type=["zip","csv","xlsx"]
)

# -----------------------------
# PROCESAR ARCHIVO
# -----------------------------

if archivo and comercio:

    df = cargar_archivo(archivo)

    if df is not None:

        st.success("Archivo cargado correctamente")

        # Mostrar columnas detectadas
        st.write("Columnas detectadas:", df.columns)

        # normalizar comercio
        df["Com_Nombre"] = df["Com_Nombre"].astype(str).str.lower()

        df = df[df["Com_Nombre"].str.contains(comercio)]

        st.write("Filas del comercio:", len(df))

        if len(df) == 0:

            st.warning("No se encontraron transacciones para ese comercio")

        else:

            # separar pagos y fees
            df_pagos = df[df["TX_reference"].astype(str).str.startswith("PY")]
            df_fees = df[df["TX_reference"].astype(str).str.startswith("SF")]

            # agrupar pagos
            pagos = df_pagos.groupby("TX_transaction_id")["TX_amount"].sum().reset_index()

            # agrupar fees
            fees = df_fees.groupby("TX_transaction_id")["OP_amount"].sum().reset_index()

            # unir pagos con fees
            df_merge = pagos.merge(fees, on="TX_transaction_id")

            df_merge["fee"] = abs(df_merge["OP_amount"])
            df_merge["monto"] = df_merge["TX_amount"]

            df_merge["porcentaje_fee"] = (df_merge["fee"] / df_merge["monto"]) * 100

            # -----------------------------
            # VOLUMEN TOTAL
            # -----------------------------

            volumen_total = df_merge["monto"].sum()

            st.subheader("Volumen total del comercio")
            st.write(volumen_total)

            # -----------------------------
            # DETECTAR BRACKET
            # -----------------------------

            fila = contrato[
                (contrato["Volumen_min"] <= volumen_total) &
                (contrato["Volumen_max"] > volumen_total)
            ]

            if not fila.empty:

                porcentaje_contrato = fila["Comision_%"].values[0]
                fija_contrato = fila["Comision_fija"].values[0]

                st.success(
                    f"Bracket aplicado: {porcentaje_contrato}% + {fija_contrato}"
                )

            else:

                st.error("No se encontró bracket para ese volumen")

                porcentaje_contrato = None

            # -----------------------------
            # VALIDAR TRANSACCIONES
            # -----------------------------

            if porcentaje_contrato is not None:

                df_merge["validacion"] = df_merge.apply(
                    lambda x: "OK"
                    if abs(x["porcentaje_fee"] - porcentaje_contrato) < 0.2
                    else "REVISAR",
                    axis=1
                )

            st.subheader("Resultados")

            st.dataframe(
                df_merge[
                    [
                        "TX_transaction_id",
                        "monto",
                        "fee",
                        "porcentaje_fee",
                        "validacion"
                    ]
                ]
            )
