from datetime import date

from wm.export import export_feedback


class FakeStore:
    def __init__(self, fb, cm):
        self._fb, self._cm = fb, cm

    def list_feedback(self):
        return self._fb

    def list_all_comments(self):
        return self._cm


FB = [{"id": 1, "advisor": "IA_1", "pagina": "Home", "categoria": "Falta un dato",
       "texto": "Quiero ver el año de ingreso", "importancia": "alta", "creado_en": "2026-10-17"}]
CM = [{"id": 1, "rut": "R1", "advisor": "IA_1", "texto": "Reunión pendiente", "creado_en": "2026-10-17"}]


def test_export_creates_two_dated_csv(tmp_path):
    paths = export_feedback(FakeStore(FB, CM), tmp_path, date(2026, 10, 17))
    assert sorted(p.name for p in paths) == ["comentarios_2026-10-17.csv", "feedback_2026-10-17.csv"]


def test_export_handles_empty_tables_with_headers_only(tmp_path):
    paths = export_feedback(FakeStore([], []), tmp_path, date(2026, 10, 17))
    for p in paths:
        lines = p.read_text(encoding="utf-8-sig").strip().splitlines()
        assert len(lines) == 1 and "advisor" in lines[0]


def test_export_is_utf8_sig_and_keeps_accents(tmp_path):
    paths = export_feedback(FakeStore(FB, CM), tmp_path, date(2026, 10, 17))
    fb = next(p for p in paths if p.name.startswith("feedback"))
    assert fb.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "año" in fb.read_text(encoding="utf-8-sig")
