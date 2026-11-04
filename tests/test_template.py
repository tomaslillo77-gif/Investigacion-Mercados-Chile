import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from make_template import build_template  # noqa: E402
from wm.columns import breakdown_columns  # noqa: E402
from wm.loader import load_dataset  # noqa: E402
from wm.quality import validate  # noqa: E402


def test_template_has_all_sheets_and_loads_empty(tmp_path):
    p = build_template(tmp_path / "plantilla.xlsx")
    ds = load_dataset(p)
    assert ds.missing_sheets == []
    assert len(ds.clientes) == 0 and len(ds.posiciones) == 0
    assert not [i for i in validate(ds) if i.level == "error"]


def test_template_carteras_include_breakdown_columns(tmp_path):
    ds = load_dataset(build_template(tmp_path / "plantilla.xlsx"))
    assert set(breakdown_columns()) <= set(ds.carteras.columns)
