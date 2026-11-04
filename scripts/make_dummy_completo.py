"""Genera los datos de ejemplo del dashboard: 100 % SINTÉTICOS, sin ningún dato de clientes ni del banco.

Salidas:
- data/Engine WM Dummy Completo.xlsx: todas las columnas del contrato, 500 clientes, casos límite (AUM cero, sin advisor,
  nombres con HTML, ISIN fuera de catálogo, RUT duplicado...), flujos por quincena, desglose por fondo, series de catálogo.
- data/Engine WM Dummy.xlsx: versión «original» más chica (99 clientes + 1 RUT repetido, sin comisiones ni flujos, con
  los montos de las posiciones como texto) para probar la lectura del formato original.

Todo sale de una semilla fija: identificadores, montos, fechas, advisors y pesos de los modelos se inventan aquí. Lo único
que viene de fuera es la lista de fondos de `scripts/dummy_catalogo_fondos.csv` (nombre, ISIN y comisión públicos).
Los nombres de cliente y advisor son en inglés y empiezan con «Dummy» para que nunca se confundan con datos reales.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wm.alignment import desvio_por_clase  # noqa: E402
from wm.columns import breakdown_columns  # noqa: E402
from wm.config import load_config  # noqa: E402
from wm.costos import costo_comision  # noqa: E402
from wm.display import advisor_names, synthetic_cliente  # noqa: E402
from wm.exposure import client_exposure, model_exposure  # noqa: E402

CATALOGO = ROOT / "scripts" / "dummy_catalogo_fondos.csv"
OUT_BASE = ROOT / "data" / "Engine WM Dummy.xlsx"
OUT = ROOT / "data" / "Engine WM Dummy Completo.xlsx"
HOY = pd.Timestamp("2026-10-17")
SERVICIOS = ["TRA", "ASE", "ADC", "Self directed", "Cartera gestionada", "Depósito a Plazo"]
TASA_COMISION = {"TRA": 0.006, "ASE": 0.010, "ADC": 0.013, "Self directed": 0.002,
                 "Cartera gestionada": 0.011, "Depósito a Plazo": 0.001}
PERIODOS = ["2026-07", "2026-08", "2026-09"]
QUINCENAS = pd.date_range(end="2026-10-12", periods=26, freq="14D")  # un año de períodos de dos semanas
N_CLIENTES = 500          # clientes inventados, para probar volumen
N_ADVISORS_EXTRA = 5
N_EDGE = 40               # los últimos N_EDGE clientes (sintéticos) reciben casos límite


def fund_breakdown(name: str, moneda: str, rng: np.random.Generator) -> dict:
    low = name.lower()
    z = dict(pct_rf_local=0.0, pct_rf_high_yield_internacional=0.0, pct_rf_investment_grade=0.0,
             pct_renta_variable=0.0, pct_rv_usa=0.0, pct_rv_latam=0.0, pct_rv_chile=0.0,
             pct_rv_emergentes=0.0, pct_rv_japon=0.0, pct_rv_europa=0.0, pct_alternativos=0.0)
    if any(k in low for k in ("private", "alternativ", "hamilton")):
        z["pct_alternativos"] = 1.0
    elif any(k in low for k in ("equity", "acciones", "s&p", "asia", "latam", "europ", "chile", "us large", "japan", "japón")):
        z["pct_renta_variable"] = 1.0
        key = ("pct_rv_chile" if "chile" in low else "pct_rv_latam" if "latam" in low else
               "pct_rv_europa" if "europ" in low else "pct_rv_japon" if "japan" in low or "japón" in low else
               "pct_rv_emergentes" if "asia" in low else "pct_rv_usa")
        z[key] = 1.0
    elif moneda == "CLP" or any(k in low for k in ("uf", "deuda")):
        z["pct_rf_local"] = 1.0
    elif "high yield" in low:
        z["pct_rf_high_yield_internacional"] = 1.0
    else:
        z["pct_rf_investment_grade"] = 1.0
    uf = round(float(rng.uniform(0.2, 0.9)) * z["pct_rf_local"], 2) if z["pct_rf_local"] else 0.0
    if moneda == "CLP":
        z.update(pct_moneda_usd=0.0, pct_moneda_clp=round(1 - uf, 2), pct_moneda_uf=uf, pct_moneda_otras=0.0)
    else:
        z.update(pct_moneda_usd=0.9, pct_moneda_clp=0.0, pct_moneda_uf=0.0, pct_moneda_otras=0.1)
    return z


PERFILES = ["Preservacion", "Defensivo", "Equilibrado", "Clasico_60_40", "Crecimiento"]
N_BASE = 99               # clientes del Excel «original» (más un RUT repetido)


def build_modelo(rng: np.random.Generator) -> pd.DataFrame:
    """Carteras modelo inventadas: de cada arquitectura se sortea qué fondos entran en cada perfil y con qué peso.
    Más riesgo = más peso a los fondos de renta variable y menos a los de renta fija; los pesos suman 100 %."""
    cat = pd.read_csv(CATALOGO)
    filas = []
    for arq, fondos in cat.groupby("arquitectura"):
        clase = {r["diccionario"]: fund_breakdown(r["diccionario"], r["moneda"], rng) for _, r in fondos.iterrows()}
        for riesgo, perfil in enumerate(PERFILES):
            elegidos = fondos[rng.random(len(fondos)) < 0.75]
            if len(elegidos) < 2:
                elegidos = fondos.head(2)
            pesos = []
            for _, f in elegidos.iterrows():
                z = clase[f["diccionario"]]
                if z["pct_renta_variable"] > 0:
                    tilt = np.exp(1.1 * (riesgo - 2))
                elif z["pct_alternativos"] > 0:
                    tilt = 0.0 if riesgo == 0 else np.exp(0.6 * (riesgo - 2))
                else:
                    tilt = np.exp(-1.1 * (riesgo - 2))
                pesos.append(rng.gamma(2.0) * tilt + 1e-6)
            pesos = np.array(pesos) / np.sum(pesos)
            for (_, f), w in zip(elegidos.iterrows(), pesos):
                filas.append({"arquitectura": arq, "perfil": perfil, "instrumento": f["instrumento"],
                              "diccionario": f["diccionario"], "isin": f["isin"], "bloomberg": f["bloomberg"],
                              "nemotecnico": f["nemotecnico"], "serie": f["serie"], "peso_objetivo": float(w),
                              "comision": f["comision"], "yield": "n.a.", "duracion": "n.a.",
                              "liquidez": int(rng.integers(1, 4)), "pct_uf": 0, "moneda": f["moneda"]})
    car = pd.DataFrame(filas)
    car["Perfil Normalizado"] = car["perfil"].str.upper()
    return car


def build_clientes_base(rng: np.random.Generator) -> pd.DataFrame:
    """Clientes inventados del Excel «original»: RUT sorteado, AUM lognormal, advisors y WM con códigos falsos."""
    ruts = [f"RUT_{int(v):08d}" for v in rng.choice(np.arange(10_000_000, 99_999_999), size=N_BASE, replace=False)]
    advisors = [f"IA_{int(v):06d}" for v in rng.choice(np.arange(100_000, 999_999), size=7, replace=False)]
    wms = [f"WM_{int(v):06d}" for v in rng.choice(np.arange(100_000, 999_999), size=4, replace=False)]
    aum = (rng.lognormal(np.log(4e8), 1.2, size=N_BASE)).round(0)
    perfil = rng.choice(PERFILES, size=N_BASE)
    return pd.DataFrame({
        "RUT": ruts, "Entidad": [f"ENTITY_{r[-6:]}" for r in ruts], "Household": [f"HH_{r[-6:]}" for r in ruts],
        "Servicio": rng.choice(SERVICIOS, size=N_BASE), "WM": rng.choice(wms, size=N_BASE),
        "IA": rng.choice(advisors, size=N_BASE), "Perfil de Riesgo": [p.replace("_", " ") for p in perfil],
        "Última Reunión": [HOY - pd.to_timedelta(int(d), unit="D") for d in rng.integers(0, 300, size=N_BASE)],
        "Valor de Mercado (CLP)": aum, "CAD (USD MM)": (aum / 950 / 1e6).round(6),
        "RUT Normalizado": ruts, "Perfil Normalizado": [p.upper() for p in perfil]})


def _clp(v) -> str:
    return "" if pd.isna(v) else f"{v:,.2f} $"


def write_base(met: pd.DataFrame, pos: pd.DataFrame, car: pd.DataFrame, rng: np.random.Generator) -> None:
    """Excel «original» sintético: los primeros N_BASE clientes + un RUT repetido, sin columnas nuevas, con montos como texto
    y depósitos a plazo sin ISIN, que es la forma que tiene el archivo real."""
    cols = ["RUT", "Entidad", "Household", "Servicio", "WM", "IA", "Perfil de Riesgo", "Última Reunión",
            "Valor de Mercado (CLP)", "CAD (USD MM)", "RUT Normalizado", "Perfil Normalizado"]
    base = met.drop_duplicates("RUT Normalizado").head(N_BASE)[cols]
    base = pd.concat([base, base.iloc[[0]]], ignore_index=True)
    p = pos[pos["RUT Normalizado"].isin(base["RUT Normalizado"])].copy()
    p = p[p["Isin"].notna() & ~p["Isin"].astype(str).str.startswith("XX")]
    p = p.rename(columns={"Cliente (ID)": "Cliente (ID)"})
    p["Valor de Mercado"] = p["VM Numérico"].map(_clp)
    p["G/P no Realizada"] = p["G/P no Realizada"].map(_clp)
    dap = base.head(20)[["RUT Normalizado"]].copy()
    dap["Cliente (ID)"] = dap["RUT Normalizado"]
    dap["Instrumento"] = [f"Dummy Time Deposit {i + 1:02d}" for i in range(len(dap))]
    dap["Tipo"] = "Renta Fija Local"
    dap["VM Numérico"] = rng.integers(20, 400, size=len(dap)) * 1_000_000
    dap["Valor de Mercado"] = dap["VM Numérico"].map(_clp)
    p = pd.concat([p, dap], ignore_index=True)
    car_base = car[car["peso_objetivo"] > 0].drop(columns=[c for c in car.columns if c not in (
        "arquitectura", "perfil", "instrumento", "diccionario", "isin", "bloomberg", "nemotecnico", "serie",
        "peso_objetivo", "comision", "yield", "duracion", "liquidez", "pct_uf", "moneda", "Perfil Normalizado")])
    car_base = car_base[~car_base["isin"].astype(str).str.startswith("SIN_ISIN")]
    with pd.ExcelWriter(OUT_BASE) as xw:
        for name, df in {"Dummy Metricas": base, "Dummy Posiciones": p, "Dummy Carteras": car_base}.items():
            pd.DataFrame([["DUMMY — SYNTHETIC DATA, NOT REAL CLIENTS"]]).to_excel(xw, sheet_name=name, index=False, header=False)
            df.to_excel(xw, sheet_name=name, index=False, startrow=2)
    print(f"OK: {OUT_BASE} ({len(base)} filas de clientes, {len(p)} posiciones)", file=sys.stderr)


def build_carteras(car: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    car = car.copy()
    sin = car["isin"].isna() | car["isin"].astype(str).str.strip().str.lower().isin(["n.a.", "n.a", "na", "nan", ""])
    car.loc[sin, "isin"] = "SIN_ISIN::" + car.loc[sin, "diccionario"].astype(str)
    car["peso_objetivo"] = car["peso_objetivo"] / car.groupby(["arquitectura", "perfil"])["peso_objetivo"].transform("sum")
    funds = car.drop_duplicates("isin")
    bd = pd.DataFrame.from_dict({r["isin"]: fund_breakdown(r["diccionario"], r["moneda"], rng)
                                 for _, r in funds.iterrows()}, orient="index").rename_axis("isin").reset_index()
    car = car.merge(bd, on="isin", how="left")
    # costo anual (TER) dummy para las series del modelo que no lo traen, según el tipo de fondo
    base = np.where(car["pct_alternativos"] > 0, 0.0120, np.where(car["pct_renta_variable"] > 0, 0.0060, 0.0040))
    car["comision"] = pd.to_numeric(car["comision"], errors="coerce")
    car["comision"] = car["comision"].where(car["comision"] > 0, base)
    # series de catálogo (peso 0), más caras que la del modelo para poder detectar series malas:
    # A = retail (1,8x) y B = intermedia (1,35x). Las posiciones del dummy usan A (_RET).
    alts = []
    for suffix, serie, mult in (("_RET", "A", 1.8), ("_B", "B", 1.35)):
        alt = car.drop_duplicates(["arquitectura", "diccionario"]).copy()
        alt["isin"] = alt["isin"] + suffix
        alt["serie"], alt["peso_objetivo"] = serie, 0.0
        alt["comision"] = (alt["comision"] * mult).round(4)
        alts.append(alt)
    car = pd.concat([car, *alts], ignore_index=True)
    # beneficio tributario de cada serie (107 LIR, 108 LIR o "-"); depende de la serie, no del cliente
    ben_rng = np.random.default_rng(108)
    isins = sorted(car["isin"].unique())
    car["beneficio_tributario"] = car["isin"].map(dict(zip(isins, ben_rng.choice(["-", "107", "108"], size=len(isins), p=[0.3, 0.3, 0.4]))))
    return car


def expand_clientes(met: pd.DataFrame, total: int) -> pd.DataFrame:
    """Suma clientes sintéticos hasta `total`: toman el perfil de un cliente base, con AUM propio (lognormal), RUT nuevo, un
    advisor entre los existentes y algunos nuevos, y a veces comparten household (varios RUT de una misma familia)."""
    if total <= len(met):
        return met
    rx = np.random.default_rng(7)
    k = total - len(met)
    base = met.iloc[rx.integers(len(met), size=k)].reset_index(drop=True).copy()
    ruts = [f"RUT_{int(v):08d}" for v in rx.choice(np.arange(10_000_000, 99_999_999), size=k, replace=False)]
    base["RUT"] = base["RUT Normalizado"] = ruts
    base["Entidad"] = [f"ENTITY_{r[-6:]}" for r in ruts]
    hh = [f"HH_{r[-6:]}" for r in ruts]
    for i in range(1, k):  # ~25 % comparte household con el cliente anterior
        if rx.random() < 0.25:
            hh[i] = hh[i - 1]
    base["Household"] = hh
    advisors = sorted(met["IA"].dropna().unique().tolist()) + [f"IA_{int(v):06d}" for v in rx.integers(100_000, 999_999, size=N_ADVISORS_EXTRA)]
    base["IA"] = rx.choice(advisors, size=k)
    factor = rx.lognormal(0, 0.9, size=k)
    for col in ("Valor de Mercado (CLP)", "CAD (USD MM)"):
        base[col] = base[col] * factor
    return pd.concat([met, base], ignore_index=True)


def edge_positions(met: pd.DataFrame, pos: pd.DataFrame) -> pd.DataFrame:
    """Casos límite en posiciones: ISIN fuera del catálogo, valor cero, G/P vacío, posición repetida y una sola posición."""
    ruts = met["RUT Normalizado"].tolist()[-N_EDGE:]
    extra = [{"Cliente (ID)": r, "Instrumento": "Fondo fuera de catálogo", "Tipo": "Fondo", "Isin": "XX0000000000",
              "VM Numérico": 50_000_000, "G/P no Realizada": 1_000_000, "Rent. no Realizada": 0.02, "RUT Normalizado": r}
             for r in ruts[7:10]]
    pos = pd.concat([pos, pd.DataFrame(extra)], ignore_index=True)
    idx = pos.index[pos["RUT Normalizado"] == ruts[10]]
    if len(idx):
        pos.loc[idx[0], ["VM Numérico", "G/P no Realizada", "Rent. no Realizada"]] = [0, 0, 0.0]
    pos.loc[pos["RUT Normalizado"] == ruts[11], ["G/P no Realizada", "Rent. no Realizada"]] = np.nan
    pos = pd.concat([pos, pos[pos["RUT Normalizado"] == ruts[12]].head(1)], ignore_index=True)
    return pos.drop(pos.index[pos["RUT Normalizado"] == ruts[13]][1:])


def edge_clients(met: pd.DataFrame) -> pd.DataFrame:
    """Casos límite en clientes: AUM cero, servicio desconocido, sin advisor y nombres con HTML, comillas o muy largos."""
    ruts = met["RUT Normalizado"].tolist()[-N_EDGE:]
    met.loc[met["RUT Normalizado"] == ruts[0], "Valor de Mercado (CLP)"] = 0
    met.loc[met["RUT Normalizado"] == ruts[1], "Servicio"] = "Servicio nuevo"
    met.loc[met["RUT Normalizado"].isin(ruts[2:4]), ["IA", "nombre_advisor"]] = np.nan
    extremos = {ruts[4]: "O'Brien & <b>Hijos</b> S.A.", ruts[5]: 'Ñandú "Ltda" $$ 100%',
                ruts[6]: "Sociedad de Inversiones " + "Muy Larga " * 12 + "SpA"}
    for r, nombre in extremos.items():
        met.loc[met["RUT Normalizado"] == r, ["nombre_cliente", "tipo_persona"]] = [nombre, "Persona jurídica"]
    return met


def main() -> None:
    rng = np.random.default_rng(42)
    met = expand_clientes(build_clientes_base(rng), N_CLIENTES)
    car = build_carteras(build_modelo(rng), rng)
    n = len(met)

    met["Servicio"] = rng.choice(SERVICIOS, size=n, p=[0.18, 0.2, 0.2, 0.17, 0.15, 0.10])
    model = car[car["peso_objetivo"] > 0]
    combos = model.groupby("arquitectura")["perfil"].unique().to_dict()
    perfil_norm = model.drop_duplicates("perfil").set_index("perfil")["Perfil Normalizado"].to_dict()

    pos_rows, arq_of, perfil_of = [], {}, {}
    for i, c in met.iterrows():
        arq = str(rng.choice(sorted(combos)))
        perfil = str(rng.choice(combos[arq]))
        arq_of[i], perfil_of[i] = arq, perfil
        if rng.random() > 0.95:
            continue  # ~5 % de clientes sin posiciones
        m = model[(model["arquitectura"] == arq) & (model["perfil"] == perfil)].groupby("isin").agg(
            w=("peso_objetivo", "sum"), d=("diccionario", "first")).reset_index()
        w = m["w"].values * rng.lognormal(0, 0.35, size=len(m))
        w = w / w.sum()
        isins = m["isin"].tolist()
        if rng.random() < 0.3:  # una posición en la serie retail (serie mala)
            j = int(rng.integers(len(isins)))
            isins[j] = isins[j] + "_RET"
        for isin, wi in zip(isins, w):
            v = float(c["Valor de Mercado (CLP)"] * wi)
            rent = float(rng.normal(0.04, 0.05))
            pos_rows.append({"Cliente (ID)": c["RUT Normalizado"], "Instrumento": isin, "Tipo": "Fondo", "Isin": isin,
                             "VM Numérico": round(v), "G/P no Realizada": round(v * rent / (1 + rent)),
                             "Rent. no Realizada": round(rent, 4), "RUT Normalizado": c["RUT Normalizado"]})
    pos = edge_positions(met, pd.DataFrame(pos_rows))
    # costo tributario dummy: impuesto estimado si se vende la posición (solo hay impuesto sobre ganancias).
    # Rng propio para no mover el resto de los datos; en producción lo entrega el cálculo tributario externo.
    tax_rng = np.random.default_rng(2026)
    pos["Costo tributario (CLP)"] = (pos["G/P no Realizada"].clip(lower=0) * tax_rng.uniform(0.10, 0.35, size=len(pos))).round(0)

    held = set(pos["RUT Normalizado"])
    met["Perfil de Riesgo"] = [perfil_of[i].replace("_", " ") for i in met.index]
    met["Perfil Normalizado"] = [perfil_norm[perfil_of[i]] for i in met.index]
    met["Última Reunión"] = [HOY - pd.to_timedelta(int(d), unit="D") if d >= 0 else pd.NaT
                            for d in rng.integers(-40, 320, size=n)]
    met["ultimo_contacto"] = [HOY - pd.to_timedelta(int(d), unit="D") for d in rng.integers(0, 260, size=n)]
    plan = rng.random(n) < 0.4
    met["tiene_wealth_plan"] = plan
    met["fecha_wealth_plan"] = [HOY - pd.to_timedelta(int(d), unit="D") if p else pd.NaT
                                for p, d in zip(plan, rng.integers(30, 700, size=n))]
    met["share_of_wallet_pct"] = rng.uniform(5, 90, size=n).round(0)
    met["arquitectura"] = [arq_of[i] if (met.loc[i, "RUT Normalizado"] in held and rng.random() < 0.4) else None for i in met.index]
    aum = met["Valor de Mercado (CLP)"]
    met["aportes_periodo"] = (aum * rng.uniform(0, 0.03, size=n)).round(0)
    met["retiros_periodo"] = (aum * rng.uniform(0, 0.025, size=n)).round(0)
    met["periodo"] = rng.choice(PERIODOS, size=n)
    met["rentabilidad_12m_pct"] = rng.normal(6.0, 3.5, size=n).round(2)
    anual = aum * met["Servicio"].map(TASA_COMISION) * rng.uniform(0.8, 1.2, size=n)
    ratio_cobrado = rng.uniform(0.25, 0.95, size=n)
    met["comision_anual_clp"] = anual.round(0)
    met["comision_cobrada_clp"] = (anual * ratio_cobrado).round(0)
    # comisión transaccional (TRA) por tipo de producto: monto anual en CLP; vacío para los demás servicios
    tarifas = load_config("tarifas")
    for producto, col in tarifas["transaccional"].items():
        tasa = tarifas["dummy_transaccional"][producto]
        met[col] = (aum * tasa * rng.uniform(0.3, 1.7, size=n)).round(0).where(met["Servicio"] == "TRA")
    nombres = met["RUT Normalizado"].map(synthetic_cliente)
    met["nombre_cliente"] = nombres.map(lambda t: t[0])
    met["tipo_persona"] = nombres.map(lambda t: t[1])
    met["nombre_advisor"] = met["IA"].map(advisor_names(met["IA"].dropna().unique().tolist()))

    # desvío vs modelo coherente con las posiciones generadas (en puntos porcentuales)
    car_cols = car.rename(columns={c: c.lower() for c in car.columns}).rename(columns={"perfil normalizado": "perfil_norm"})
    pos_calc = pos.rename(columns={"Isin": "isin", "VM Numérico": "valor_clp", "RUT Normalizado": "rut"})
    by_rut = {r: g for r, g in pos_calc.groupby("rut")}
    desvio = []
    for i, c in met.iterrows():
        g = by_rut.get(c["RUT Normalizado"])
        if g is None:
            desvio.append(np.nan)
            continue
        d = desvio_por_clase(client_exposure(g, car_cols), model_exposure(car_cols, arq_of[i], perfil_of[i]))
        desvio.append(round(d[max(d, key=lambda k: abs(d[k]))], 1) if d else np.nan)
    met["desvio_modelo_pct"] = desvio

    # la comisión anual de ADC/ASE/TRA es la misma que muestra la ficha (fondos + asesoría, o transaccional)
    tra_cols = list(tarifas["transaccional"].values())
    for i, c in met.iterrows():
        row = pd.Series({"servicio": c["Servicio"], "aum_clp": c["Valor de Mercado (CLP)"], **{k: c[k] for k in tra_cols}})
        g = by_rut.get(c["RUT Normalizado"], pos_calc.iloc[0:0])
        if c["Servicio"] in tarifas["asesoria"] and g.empty:
            continue
        costo = costo_comision(row, g, car_cols)
        if costo is not None:
            met.loc[i, "comision_anual_clp"] = round(costo.total)
            met.loc[i, "comision_cobrada_clp"] = round(costo.total * ratio_cobrado[i])

    # flujos por cliente y quincena: la mayoría de los períodos sin movimiento, con aportes y retiros del orden de 0-0,6 % del AUM
    flow_rng = np.random.default_rng(14)
    rows = []
    for _, c in met.iterrows():
        for q in QUINCENAS:
            ap = c["Valor de Mercado (CLP)"] * flow_rng.uniform(0, 0.006) * (flow_rng.random() < 0.45)
            re_ = c["Valor de Mercado (CLP)"] * flow_rng.uniform(0, 0.005) * (flow_rng.random() < 0.35)
            rows.append({"RUT Normalizado": c["RUT Normalizado"], "Periodo": q, "Aportes (CLP)": round(ap), "Retiros (CLP)": round(re_)})
    flujos = pd.DataFrame(rows)

    met = edge_clients(met)
    met = pd.concat([met, met.iloc[[0]]], ignore_index=True)  # un RUT repetido: debe salir en Calidad de datos
    with pd.ExcelWriter(OUT) as xw:
        for name, df in {"Dummy Metricas": met, "Dummy Posiciones": pos, "Dummy Carteras": car, "Dummy Flujos": flujos}.items():
            pd.DataFrame([["DUMMY COMPLETE — SYNTHETIC DATA TO TEST THE DASHBOARD, NOT REAL CLIENTS"]]).to_excel(
                xw, sheet_name=name, index=False, header=False)
            df.to_excel(xw, sheet_name=name, index=False, startrow=2)
    print(f"OK: {OUT} ({len(met)} clientes, {len(pos)} posiciones, {len(car)} filas de carteras)", file=sys.stderr)
    write_base(met, pos, car, np.random.default_rng(99))


if __name__ == "__main__":
    main()
