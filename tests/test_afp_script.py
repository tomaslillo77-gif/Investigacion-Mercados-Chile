import pandas as pd

from scripts.actualizar_afp import main
from wm.afp.fuente import FONDOS


def _csv(fin="2026-10-15"):
    fechas = pd.date_range(end=fin, periods=5, freq="D")
    return "Fecha;X;Y\n" + "\n".join(f"{d:%Y-%m-%d};100,5;200,25" for d in fechas) + "\n"


def _leer_ok(url):
    return _csv()


def test_guarda_la_foto_y_devuelve_0(tmp_path):
    assert main(["--out", str(tmp_path)], leer=_leer_ok) == 0
    assert (tmp_path / "2026-10-15" / "valor_cuota.csv").exists()
    assert (tmp_path / "2026-10-15" / "patrimonio.csv").exists()


def test_repo_caido_no_toca_la_ultima_foto(tmp_path, capsys):
    main(["--out", str(tmp_path)], leer=_leer_ok)
    antes = (tmp_path / "2026-10-15" / "valor_cuota.csv").read_bytes()

    def caido(url):
        raise OSError("sin red")
    assert main(["--out", str(tmp_path)], leer=caido) == 1
    assert (tmp_path / "2026-10-15" / "valor_cuota.csv").read_bytes() == antes
    assert "2026-10-15" in capsys.readouterr().out


def test_respuesta_html_retorna_1_sin_escribir(tmp_path):
    assert main(["--out", str(tmp_path)], leer=lambda url: "<html>404</html>") == 1
    assert list(tmp_path.iterdir()) == []


def test_fechas_desalineadas_retorna_1_sin_escribir(tmp_path):
    def desalineado(url):
        return _csv("2026-10-14") if url.endswith("patfC.csv") else _csv()
    assert main(["--out", str(tmp_path)], leer=desalineado) == 1
    assert list(tmp_path.iterdir()) == []


def test_sin_fotos_previas_y_repo_caido_dice_que_no_hay(tmp_path, capsys):
    def caido(url):
        raise OSError("sin red")
    assert main(["--out", str(tmp_path)], leer=caido) == 1
    assert "no hay" in capsys.readouterr().out.lower()
