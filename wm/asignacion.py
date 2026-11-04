"""Reasignación de clientes entre advisors. El Excel es la fuente; el Managing Director puede cambiar el advisor desde el portal y el cambio se
superpone al cargar los datos. Mientras el Excel no traiga el cambio, queda «pendiente en el Excel»: se descarga la lista para que el dueño de la fuente la aplique."""
from dataclasses import replace
from io import BytesIO

import pandas as pd

from wm.loader import Dataset

PENDIENTE, REFLEJADA = "Pendiente en el Excel", "Reflejada en el Excel"


def aplicar_asignaciones(ds: Dataset, vigentes: pd.DataFrame | None) -> Dataset:
    """Dataset donde cada cliente reasignado tiene el advisor nuevo. Agrega `advisor_excel` (lo que dice el Excel hoy) y `asignacion_pendiente`
    (True si el advisor del portal difiere del Excel). Un RUT que no está en los datos se ignora."""
    if vigentes is None or vigentes.empty or "advisor" not in ds.clientes.columns:
        return ds
    clientes = ds.clientes.copy()
    nuevo = vigentes.drop_duplicates("rut", keep="last").set_index("rut")["advisor"].to_dict()
    clientes["advisor_excel"] = clientes["advisor"]
    clientes["advisor"] = [nuevo.get(r, a) for r, a in zip(clientes["rut"], clientes["advisor"])]
    clientes["asignacion_pendiente"] = [(r in nuevo) and (nuevo[r] != a) for r, a in zip(clientes["rut"], clientes["advisor_excel"])]
    return replace(ds, clientes=clientes)


def cambios(view: pd.DataFrame, vigentes: pd.DataFrame | None, nombre) -> pd.DataFrame:
    """Reasignaciones vigentes de clientes que están en los datos: cliente, advisor en el Excel, advisor nuevo, quién, cuándo, motivo y estado.
    `nombre` convierte un código de advisor en su nombre."""
    cols = ["RUT", "Cliente", "Advisor en el Excel", "Advisor nuevo", "Cambiado por", "Fecha", "Motivo", "Estado"]
    if vigentes is None or vigentes.empty or "advisor_excel" not in view.columns:
        return pd.DataFrame(columns=cols)
    v = vigentes.drop_duplicates("rut", keep="last").merge(view.drop_duplicates("rut")[["rut", "cliente_label", "advisor_excel"]].rename(columns={"advisor_excel": "_excel_hoy"}), on="rut")
    if v.empty:
        return pd.DataFrame(columns=cols)
    pend = v["advisor"] != v["_excel_hoy"]
    out = pd.DataFrame({"RUT": v["rut"], "Cliente": v["cliente_label"], "Advisor en el Excel": v["_excel_hoy"].map(nombre), "Advisor nuevo": v["advisor"].map(nombre),
                        "Cambiado por": v["cambiado_por"], "Fecha": pd.to_datetime(v["creado_en"]).dt.strftime("%d-%m-%Y %H:%M"), "Motivo": v["motivo"],
                        "Estado": pend.map({True: PENDIENTE, False: REFLEJADA})})
    orden = pd.DataFrame({"p": pend.values, "f": pd.to_datetime(v["creado_en"]).values}).sort_values(["p", "f"], ascending=[False, False]).index
    return out.iloc[orden].reset_index(drop=True)[cols]


def excel_reasignaciones(c: pd.DataFrame, historial: pd.DataFrame | None = None) -> bytes:
    """Excel para el dueño de la fuente: hoja «Pendientes» (lo que hay que cambiar en el Excel) e «Historial» de todos los cambios."""
    def sin_zona(df: pd.DataFrame) -> pd.DataFrame:   # Excel no admite fechas con zona horaria
        df = df.copy()
        for col in df.columns:
            if isinstance(df[col].dtype, pd.DatetimeTZDtype):
                df[col] = df[col].dt.tz_localize(None)
        return df

    c, historial = sin_zona(c), None if historial is None else sin_zona(historial)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        c[c["Estado"] == PENDIENTE].to_excel(w, sheet_name="Pendientes", index=False)
        (c if historial is None else historial).to_excel(w, sheet_name="Historial", index=False)
    return buf.getvalue()
