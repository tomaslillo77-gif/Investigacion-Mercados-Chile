"""Tema editorial sobrio, orientado al cliente, con paleta inspirada en Scotiabank:
blanco y gris neutro, tinta carbón, titulares en serif y el rojo solo como firma (barra superior,
ítem activo, botones, enlaces). Contraste verificado en tests/test_theme.py.
Los hex son una aproximación a la marca: validar contra la guía de marca oficial del banco."""
import streamlit as st

BG = "#FFFFFF"            # lienzo
CARD = "#FFFFFF"          # superficies
PANEL = "#F5F5F6"         # menú lateral y cabeceras de tabla
BORDER = "#D8D8DC"        # líneas finas
TEXT = "#1F1F21"          # tinta
MUTED = "#66666B"
SIDEBAR = PANEL
ON_SIDEBAR = TEXT
ACCENT = "#EC111A"        # rojo de marca
ACCENT_DEEP = "#B50E15"   # rojo para texto y enlaces sobre blanco
SERIE_1 = "#3B3B3F"       # serie principal en gráficos (cliente, aportes)
SERIE_2 = "#2E6DA4"       # serie de comparación (modelo, neto)
# prioridad de color en gráficos: rojo, azul, gris y negro; después el resto
GRIS = "#8A8A90"
NEGRO = "#3B3B3F"
PALETTE = [ACCENT, SERIE_2, GRIS, NEGRO, "#00857C", "#B7791F", "#7B3F8C"]
# exposiciones (clases de activo y monedas): rojo, azul y gris como colores primarios, en ese orden de prioridad
EXPO_PALETTE = PALETTE
# Cambria/Charter usan cifras de altura uniforme (Georgia no: sus cifras de estilo antiguo desalinean montos)
DISPLAY = "Charter, 'Bitstream Charter', Cambria, 'Times New Roman', Times, serif"

CSS = f"""
<style>
    .stApp {{ background: {BG}; color: {TEXT}; font-variant-numeric: lining-nums tabular-nums; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    div[data-testid="stDecoration"] {{ display: block; height: 4px; background: {ACCENT}; }}
    .block-container {{ padding-top: 2.5rem; max-width: 1400px; }}
    h1, h2, h3, h4 {{ color: {TEXT}; font-family: {DISPLAY}; font-weight: 500; }}
    a {{ color: {ACCENT_DEEP}; }}
    :focus-visible {{ outline: 2px solid {TEXT}; outline-offset: 2px; }}

    /* menú lateral: gris neutro, la marca es la barra roja superior */
    section[data-testid="stSidebar"] {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
    section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] summary,
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{ color: {ON_SIDEBAR}; }}
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: 13px; color: {MUTED}; }}
    section[data-testid="stSidebar"] details {{ border: 1px solid {BORDER}; border-radius: 2px; background: {CARD}; }}
    div[data-testid="stPopover"] {{ display:flex; justify-content:flex-end; }}
    .nav-section {{ font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:{MUTED}; margin:14px 0 4px 0; }}
    .brand {{ font-family: {DISPLAY}; font-size: 24px; font-weight: 500; color: {TEXT}; padding: 4px 0 0 0; line-height: 1.1; }}
    .brand-sub {{ font-family: {DISPLAY}; font-size: 24px; color: {TEXT}; line-height: 1.1; margin-bottom: 4px; }}
    .brand-sub::after {{ content: ""; display: block; width: 32px; height: 3px; background: {ACCENT}; margin: 14px 0 18px 0; }}
    .tag {{ border: 1px solid {BORDER}; background: {CARD}; color: {MUTED}; border-radius: 2px; padding: 8px 12px; font-size: 12px; margin: 8px 0; }}
    section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 0; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label {{
        padding: 9px 12px; border-left: 3px solid transparent; width: 100%; cursor: pointer; border-radius: 0; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{ display: none; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: {BORDER}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
        background: {CARD}; border-left-color: {ACCENT}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ font-weight: 700; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label p {{ font-size: 15px; color: {TEXT}; }}

    /* secciones: sin cajas; una línea fina y aire. Streamlit envuelve TODOS los bloques en este wrapper y solo las
       secciones (border=True) no llevan la clase st-emotion-cache-0 (verificado en Streamlit 1.40.2, fijada en requirements.txt). */
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background: transparent; border: 0 !important; box-shadow: none; }}
    div[data-testid="stVerticalBlockBorderWrapper"]:not(.st-emotion-cache-0) {{
        border-top: 1px solid {BORDER} !important; border-radius: 0; padding: 1.4rem 0 1rem 0; margin-top: 0.6rem; }}
    .card-title {{ font-family: {DISPLAY}; font-size: 24px; font-weight: 500; color: {TEXT}; margin-bottom: 4px; }}
    .chart-title {{ font-family: {DISPLAY}; font-size: 18px; font-weight: 500; color: {TEXT}; margin: 18px 0 0 0; }}
    .section-title {{ font-family: {DISPLAY}; font-size: 22px; font-weight: 500; margin: 14px 0 8px 0; }}
    .page-title {{ font-family: {DISPLAY}; font-size: 40px; font-weight: 400; letter-spacing: -0.5px; color: {TEXT}; margin-bottom: 18px; line-height: 1.1; }}
    .page-rule {{ display: none; }}
    .hello {{ font-size: 15px; color: {MUTED}; margin-bottom: -2px; }}
    .hello-name {{ font-family: {DISPLAY}; font-size: 44px; font-weight: 400; letter-spacing: -0.5px; color: {TEXT}; margin-bottom: 10px; line-height: 1.1; }}
    .big-value {{ font-family: {DISPLAY}; font-size: 34px; color: {TEXT}; line-height: 1.15; margin-bottom: 6px; }}
    .espacio {{ height: 24px; }}  /* separador vertical entre bloques de una misma tarjeta */
    .stat-label {{ font-size: 13px; color: {MUTED}; }}
    .stat-value {{ font-family: {DISPLAY}; font-size: 28px; white-space: nowrap; font-weight: 400; color: {TEXT}; line-height: 1.2; }}
    .footnote.field-note {{ margin-top: -0.5rem; }}  /* la nota queda pegada al campo que describe, no a la etiqueta siguiente */
    .footnote {{ font-size: 12px; color: {MUTED}; margin-top: 8px; max-width: 90ch; }}
    .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:9px; }}
    .legend-row {{ display:flex; justify-content:space-between; font-size:13px; padding:6px 0; border-bottom: 1px solid {BORDER}; }}
    .legend-row span:last-child {{ color:{TEXT}; }}
    .legend-row.legend-sub {{ padding:3px 0 3px 19px; font-size:12px; color:{MUTED}; }}
    .legend-row.legend-sub span:last-child {{ color:{MUTED}; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:2px; font-size:12px; font-weight:600; }}
    .badge-warn {{ background:#FFF1D6; color:#7A4E00; }}
    .badge-ok {{ background:#DDF3E4; color:#0B5D2A; }}
    .badge-bad {{ background:#FDE3E4; color:{ACCENT_DEEP}; }}
    .badge-muted {{ background:{PANEL}; color:#4A4A4F; }}
    .chip {{ display:inline-block; padding:2px 8px; margin:0 4px 2px 0; border-radius:2px; font-size:12px; background:{PANEL}; color:{TEXT}; }}
    .callout {{ border-left: 3px solid {TEXT}; background:{PANEL}; padding:12px 16px; margin:8px 0; }}
    .callout.warn {{ border-left-color:#B7791F; }}
    .callout.ok {{ border-left-color:#0B5D2A; }}
    .callout.info {{ border-left-color:{SERIE_2}; }}
    .pending {{ border:1px dashed #B5B5BB; padding:14px; color:{MUTED}; font-size:13px; }}
    .comment {{ border-left:3px solid {ACCENT}; padding:4px 12px; margin:8px 0; }}
    .comment .meta {{ font-size:12px; color:{MUTED}; }}

    /* tablas: sin relleno, encabezado con línea de tinta, filas con línea fina */
    table.dtable {{ width:100%; border-collapse:collapse; font-size:13px; }}
    table.dtable, table.dtable th, table.dtable td {{ border: 0; }}
    table.dtable th {{ background:transparent; color:{MUTED}; font-weight:600; font-size:12px; text-align:center; padding:10px 12px;
                       border-bottom: 1px solid {TEXT}; }}
    table.dtable td {{ padding:11px 12px; border-bottom:1px solid {BORDER}; color:{TEXT}; }}
    table.dtable tr.total td {{ font-weight:700; background:{PANEL}; border-top: 1px solid {TEXT}; }}
    table.dtable tr.clase td {{ background:#FDECEC; color:{ACCENT_DEEP}; font-weight:700; border-bottom:1px solid #F4B9BC; }}
    table.dtable td, table.dtable th.num {{ text-align:center; }}
    table.dtable th:first-child, table.dtable td:first-child {{ text-align:left; }}
    table.dtable td a, table.dtable td.link {{ color:{TEXT}; font-weight:600; }}

    /* controles */
    div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="textarea"],
    div[data-baseweb="base-input"] {{ background:{CARD}; border: 1px solid #B5B5BB !important; border-radius: 2px; }}
    /* en la barra lateral el selector de rol no se escribe: sin cursor parpadeante */
    section[data-testid="stSidebar"] div[data-baseweb="select"] input {{ caret-color: transparent; cursor: pointer; }}
    .stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input {{ color:{TEXT}; }}
    .stButton > button, .stDownloadButton > button {{ background:{ACCENT}; color:#fff; border:0; border-radius:2px; font-weight:600; padding: 0.45rem 1.1rem; }}
    .stButton > button:hover, .stDownloadButton > button:hover {{ background:{ACCENT_DEEP}; color:#fff; }}
    .stButton > button:disabled {{ background:#C9C9CE; color:#fff; }}
    div[data-testid="stExpander"] details {{ border: 1px solid {BORDER}; border-radius: 2px; }}
    div[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; }}
    hr {{ border-color:{BORDER}; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def inject_extra_css() -> None:  # compatibilidad: los estilos adicionales ya están en CSS
    return None
