import streamlit as st
import pandas as pd
import zipfile

st.title("Comparador de Comisiones por Contrato")

# -----------------------------
# Configuración manual contrato
# -----------------------------

st.subheader("Configuración del contrato")

contrato = pd.DataFrame({
    "Volumen_min": [0,500000,2000000,4000000],
    "Volumen_max": [500000,2000000,4000000,999999999],
    "Comision_%": [2.30,2.10,1.90,1.80],
    "Comision_fija": [0.90,0.90,0.90,0.90]
})

contrato = st.data_editor(contrato)

st.write("Tabla del contrato configurada:")
st.dataframe(contrato)

# -----------------------------
# Seleccionar comercio
# -----------------------------

comercio = st.text_input("Nombre del comercio (ej: pay retailers)").lower()

# -----------------------------
# Cargar archivo
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

archivo = st.file_uploader(
    "Subir archivo de transacciones",
    type=["zip","csv","xlsx"]
)

# -----------------------------
# Procesar archivo
# -----------------------------

if archivo and comercio:

    df = cargar_archivo(archivo)

    if df is not None:

        st.success("Archivo cargado correctamente")

        # normalizar comercio
        df["Com_Nom"] = df["Com_Nom"].astype(str).str.lower()

        df = df[df["Com_Nom"].str.contains(comercio)]

        st.write("Filas del comercio:", len(df))

        if len(df) == 0:

            st.warning("No se encontraron transacciones")

        else:

            # separar pagos y fees
            df_pagos = df[df["TX_reference"].astype(str).str.startswith("PY")]
            df_fees = df[df["TX_reference"].astype(str).str.startswith("SF")]

            # agrupar pagos
            pagos = df_pagos.groupby("TX_transaction_id")["TX_amount"].sum().reset_index()

            # agrupar fees
            fees = df_fees.groupby("TX_transaction_id")["OP_amount"].sum().reset_index()

            # unir
            df_merge = pagos.merge(fees,on="TX_transaction_id")

            df_merge["fee"] = abs(df_merge["OP_amount"])
            df_merge["monto"] = df_merge["TX_amount"]

            df_merge["porcentaje_fee"] = (df_merge["fee"] / df_merge["monto"]) * 100

            # -----------------------------
            # calcular volumen total
            # -----------------------------

            volumen_total = df_merge["monto"].sum()

            st.write("Volumen total:", volumen_total)

            # -----------------------------
            # detectar bracket contrato
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

                st.error("No se encontró bracket para el volumen")

                porcentaje_contrato = None
                fija_contrato = None

            # -----------------------------
            # validar transacciones
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
