from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class StoreUnavailable(Exception):
    pass


class ConflictoDeVersion(Exception):
    """Otro advisor guardó un portafolio del mismo cliente después de que éste lo leyó. Trae la versión que quedó vigente."""

    def __init__(self, version_actual: int):
        self.version_actual = version_actual
        super().__init__(f"El portafolio ya está en la versión {version_actual}.")


class Store:
    """Persistencia de comentarios, datos capturados y feedback en PostgreSQL local."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextmanager
    def _conn(self):
        try:
            with psycopg.connect(self.dsn, connect_timeout=3, row_factory=dict_row) as conn:
                yield conn
        except psycopg.Error as e:
            raise StoreUnavailable(str(e)) from e

    def available(self) -> bool:
        try:
            with self._conn() as c:
                c.execute("SELECT 1")
            return True
        except StoreUnavailable:
            return False

    def migrate(self) -> None:
        with self._conn() as c:
            c.execute(SCHEMA.read_text(encoding="utf-8"))

    def add_comment(self, rut: str, advisor: str, texto: str) -> int:
        with self._conn() as c:
            return c.execute(
                "INSERT INTO comentarios_cliente (rut, advisor, texto) VALUES (%s,%s,%s) RETURNING id",
                (rut, advisor, texto)).fetchone()["id"]

    def list_comments(self, rut: str) -> list[dict]:
        with self._conn() as c:
            return c.execute("SELECT * FROM comentarios_cliente WHERE rut=%s ORDER BY id", (rut,)).fetchall()

    def list_all_comments(self) -> list[dict]:
        with self._conn() as c:
            return c.execute("SELECT * FROM comentarios_cliente ORDER BY id").fetchall()

    def set_dato(self, rut: str, campo: str, valor: str, advisor: str) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO datos_cliente (rut, campo, valor, advisor) VALUES (%s,%s,%s,%s)",
                      (rut, campo, valor, advisor))

    def get_datos(self, rut: str) -> dict[str, dict]:
        with self._conn() as c:
            rows = c.execute("SELECT DISTINCT ON (campo) campo, valor, advisor, actualizado_en "
                             "FROM datos_cliente WHERE rut=%s ORDER BY campo, id DESC", (rut,)).fetchall()
        return {r["campo"]: r for r in rows}

    def dato_history(self, rut: str, campo: str) -> list[dict]:
        with self._conn() as c:
            return c.execute("SELECT * FROM datos_cliente WHERE rut=%s AND campo=%s ORDER BY id",
                             (rut, campo)).fetchall()

    def add_feedback(self, advisor: str, pagina: str, categoria: str, texto: str, importancia: str) -> int:
        with self._conn() as c:
            return c.execute(
                "INSERT INTO feedback (advisor, pagina, categoria, texto, importancia) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (advisor, pagina, categoria, texto, importancia)).fetchone()["id"]

    def list_feedback(self) -> list[dict]:
        with self._conn() as c:
            return c.execute("SELECT * FROM feedback ORDER BY id").fetchall()

    def latest_by_campo(self, campo: str) -> dict[str, dict]:
        with self._conn() as c:
            rows = c.execute("SELECT DISTINCT ON (rut) rut, valor, advisor, actualizado_en "
                             "FROM datos_cliente WHERE campo=%s ORDER BY rut, id DESC", (campo,)).fetchall()
        return {r["rut"]: r for r in rows}

    # ── Portafolio objetivo del cliente (versiones inmutables; la vigente es la última) ───────────────────────────────────────────────────
    def guardar_portafolio(self, rut: str, items: pd.DataFrame, advisor: str, nota: str = "", origen: str = "vacio",
                           perfil_al_guardar: str | None = None, version_base: int = 0) -> int:
        """Guarda una versión nueva y la deja vigente. `version_base` es la versión que el advisor tenía a la vista (0 si no había): si mientras tanto
        alguien guardó otra, lanza ConflictoDeVersion y no escribe nada. Todo ocurre en una transacción: o se guarda completo o no se guarda."""
        filas = [(r["instrument_id"], None if pd.isna(r["isin"]) else str(r["isin"]), str(r["nombre"]), None if pd.isna(r["serie"]) else str(r["serie"]),
                  float(r["peso"]), None if pd.isna(r["comision"]) else float(r["comision"]), n) for n, (_, r) in enumerate(items.iterrows())]
        with self._conn() as c:
            ultima = c.execute("SELECT version FROM portafolio_cliente WHERE rut=%s ORDER BY version DESC LIMIT 1 FOR UPDATE", (rut,)).fetchone()
            actual = ultima["version"] if ultima else 0
            if actual != version_base:
                raise ConflictoDeVersion(actual)
            try:
                c.execute("UPDATE portafolio_cliente SET vigente=FALSE WHERE rut=%s AND vigente", (rut,))
                nueva = actual + 1
                pid = c.execute("INSERT INTO portafolio_cliente (rut, version, advisor, nota, origen, perfil_al_guardar) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                                (rut, nueva, advisor, nota, origen, perfil_al_guardar)).fetchone()["id"]
            except UniqueViolation:   # otro guardó la primera versión al mismo tiempo
                raise ConflictoDeVersion(actual + 1) from None
            with c.cursor() as cur:
                cur.executemany("INSERT INTO portafolio_cliente_item (portafolio_id, instrument_id, isin, nombre, serie, peso, comision, orden) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", [(pid, *f) for f in filas])
        return nueva

    @staticmethod
    def _items(filas: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(filas, columns=["instrument_id", "isin", "nombre", "serie", "peso", "comision"])
        df["peso"] = df["peso"].astype(float)
        df["comision"] = pd.to_numeric(df["comision"], errors="coerce")
        return df

    def portafolio_version(self, rut: str, version: int) -> dict | None:
        with self._conn() as c:
            p = c.execute("SELECT * FROM portafolio_cliente WHERE rut=%s AND version=%s", (rut, version)).fetchone()
            if p is None:
                return None
            it = c.execute("SELECT instrument_id, isin, nombre, serie, peso, comision FROM portafolio_cliente_item WHERE portafolio_id=%s ORDER BY orden", (p["id"],)).fetchall()
        return {**p, "items": self._items(it)}

    def portafolio_vigente(self, rut: str) -> dict | None:
        with self._conn() as c:
            p = c.execute("SELECT version FROM portafolio_cliente WHERE rut=%s AND vigente", (rut,)).fetchone()
        return self.portafolio_version(rut, p["version"]) if p else None

    def historial_portafolio(self, rut: str) -> list[dict]:
        """Metadatos de todas las versiones del cliente, la más reciente primero (sin los ítems)."""
        with self._conn() as c:
            return c.execute("SELECT p.id, p.version, p.advisor, p.creado_en, p.nota, p.origen, p.perfil_al_guardar, p.vigente, "
                             "(SELECT count(*) FROM portafolio_cliente_item i WHERE i.portafolio_id = p.id) AS n_items "
                             "FROM portafolio_cliente p WHERE p.rut=%s ORDER BY p.version DESC", (rut,)).fetchall()

    def portafolios_vigentes(self) -> pd.DataFrame:
        """Todos los portafolios vigentes, una fila por instrumento: rut, version, advisor, creado_en, perfil_al_guardar + las columnas del ítem."""
        with self._conn() as c:
            rows = c.execute("SELECT p.rut, p.version, p.advisor, p.creado_en, p.perfil_al_guardar, i.instrument_id, i.isin, i.nombre, i.serie, i.peso, i.comision "
                             "FROM portafolio_cliente p JOIN portafolio_cliente_item i ON i.portafolio_id = p.id WHERE p.vigente ORDER BY p.rut, i.orden").fetchall()
        df = pd.DataFrame(rows, columns=["rut", "version", "advisor", "creado_en", "perfil_al_guardar", "instrument_id", "isin", "nombre", "serie", "peso", "comision"])
        df["peso"] = df["peso"].astype(float)
        df["comision"] = pd.to_numeric(df["comision"], errors="coerce")
        return df

    def resumen_portafolios_vigentes(self) -> pd.DataFrame:
        """Una fila por cliente con portafolio vigente: rut, version, advisor, creado_en, perfil_al_guardar, n_items."""
        with self._conn() as c:
            rows = c.execute("SELECT p.rut, p.version, p.advisor, p.creado_en, p.perfil_al_guardar, "
                             "(SELECT count(*) FROM portafolio_cliente_item i WHERE i.portafolio_id = p.id) AS n_items "
                             "FROM portafolio_cliente p WHERE p.vigente ORDER BY p.rut").fetchall()
        return pd.DataFrame(rows, columns=["rut", "version", "advisor", "creado_en", "perfil_al_guardar", "n_items"])

    # ── Reasignación de clientes entre advisors ─────────────────────────────────────────────────────────────────────────────────────────
    def reasignar(self, rut: str, advisor: str, por: str, motivo: str = "", advisor_excel: str | None = None) -> int:
        """Deja `advisor` como el advisor vigente del cliente (la asignación anterior queda en el historial). Devuelve el id del cambio."""
        with self._conn() as c:
            with c.transaction():
                c.execute("SELECT 1 FROM asignacion_cliente WHERE rut=%s AND vigente FOR UPDATE", (rut,))
                c.execute("UPDATE asignacion_cliente SET vigente=FALSE WHERE rut=%s AND vigente", (rut,))
                return c.execute("INSERT INTO asignacion_cliente (rut, advisor, advisor_excel, cambiado_por, motivo) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                                 (rut, advisor, advisor_excel, por, motivo)).fetchone()["id"]

    def asignaciones_vigentes(self) -> pd.DataFrame:
        """Una fila por cliente reasignado: id, rut, advisor, advisor_excel, cambiado_por, motivo, creado_en."""
        with self._conn() as c:
            rows = c.execute("SELECT id, rut, advisor, advisor_excel, cambiado_por, motivo, creado_en FROM asignacion_cliente WHERE vigente ORDER BY rut").fetchall()
        return pd.DataFrame(rows, columns=["id", "rut", "advisor", "advisor_excel", "cambiado_por", "motivo", "creado_en"])

    def historial_asignaciones(self, rut: str | None = None) -> pd.DataFrame:
        """Todos los cambios (de un cliente o de todos), el más reciente primero."""
        with self._conn() as c:
            rows = c.execute("SELECT id, rut, advisor, advisor_excel, cambiado_por, motivo, creado_en, vigente FROM asignacion_cliente "
                             + ("WHERE rut=%s " if rut else "") + "ORDER BY id DESC", (rut,) if rut else ()).fetchall()
        return pd.DataFrame(rows, columns=["id", "rut", "advisor", "advisor_excel", "cambiado_por", "motivo", "creado_en", "vigente"])
