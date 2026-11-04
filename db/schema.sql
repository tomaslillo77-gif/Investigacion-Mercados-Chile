CREATE TABLE IF NOT EXISTS comentarios_cliente (
    id         SERIAL PRIMARY KEY,
    rut        TEXT NOT NULL,
    advisor    TEXT NOT NULL,
    texto      TEXT NOT NULL,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_comentarios_rut ON comentarios_cliente (rut, id);

CREATE TABLE IF NOT EXISTS datos_cliente (
    id             SERIAL PRIMARY KEY,
    rut            TEXT NOT NULL,
    campo          TEXT NOT NULL,
    valor          TEXT NOT NULL,
    advisor        TEXT NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_datos_rut_campo ON datos_cliente (rut, campo, id);

CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL PRIMARY KEY,
    advisor     TEXT NOT NULL,
    pagina      TEXT NOT NULL,
    categoria   TEXT NOT NULL,
    texto       TEXT NOT NULL,
    importancia TEXT NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Portafolio objetivo de cada cliente, definido por el advisor. Cada guardado crea una versión nueva e inmutable; la vigente es la última.
CREATE TABLE IF NOT EXISTS portafolio_cliente (
    id                SERIAL PRIMARY KEY,
    rut               TEXT NOT NULL,
    version           INT NOT NULL,
    advisor           TEXT NOT NULL,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now(),
    nota              TEXT NOT NULL DEFAULT '',
    origen            TEXT NOT NULL DEFAULT 'vacio',   -- 'hoy' | 'modelo:<arquitectura>/<perfil>' | 'version:<n>' | 'vacio' | 'excel'
    perfil_al_guardar TEXT,
    vigente           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (rut, version)
);
-- a lo más una versión vigente por cliente (lo garantiza la base, no solo el código)
CREATE UNIQUE INDEX IF NOT EXISTS uq_portafolio_vigente ON portafolio_cliente (rut) WHERE vigente;

CREATE TABLE IF NOT EXISTS portafolio_cliente_item (
    portafolio_id INT NOT NULL REFERENCES portafolio_cliente (id) ON DELETE CASCADE,
    instrument_id TEXT NOT NULL,
    isin          TEXT,
    nombre        TEXT NOT NULL,                       -- copia al guardar: el historial no cambia si el catálogo cambia después
    serie         TEXT,
    peso          NUMERIC(8, 4) NOT NULL CHECK (peso >= 0 AND peso <= 100),   -- en puntos porcentuales
    comision      NUMERIC,
    orden         INT NOT NULL DEFAULT 0,
    PRIMARY KEY (portafolio_id, instrument_id)
);

-- Reasignación de un cliente a otro advisor, hecha por el Managing Director. Se superpone al advisor que trae el Excel; cada cambio queda en el historial.
-- `advisor_excel` es lo que decía el Excel al momento del cambio (sirve para el aviso de «pendiente en el Excel»).
CREATE TABLE IF NOT EXISTS asignacion_cliente (
    id            SERIAL PRIMARY KEY,
    rut           TEXT NOT NULL,
    advisor       TEXT NOT NULL,
    advisor_excel TEXT,
    cambiado_por  TEXT NOT NULL,
    motivo        TEXT NOT NULL DEFAULT '',
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    vigente       BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_asignacion_vigente ON asignacion_cliente (rut) WHERE vigente;
