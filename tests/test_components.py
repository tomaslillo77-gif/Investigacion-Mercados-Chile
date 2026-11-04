from datetime import datetime

import pandas as pd

from ui.components import Raw, badge, html_table, money


def test_money_clp_thousands_separator():
    assert money(1234567, "CLP") == "$1,234,567"


def test_money_usd_in_millions():
    assert money(3_310_000, "USD") == "US$3.31 MM"


def test_money_nan_is_dash():
    assert money(float("nan"), "CLP") == "—"


def test_badge_html_contains_text_and_kind_class():
    b = badge("Sí", "warn")
    assert "badge-warn" in b and "Sí" in b and isinstance(b, Raw)


def test_html_table_escapes_html_in_cells():
    df = pd.DataFrame({"Cliente": ["<script>alert(1)</script>"]})
    out = html_table(df)
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_html_table_keeps_raw_badges():
    df = pd.DataFrame({"Estado": [badge("Ok", "ok")]})
    assert "badge-ok" in html_table(df)


def test_html_table_total_row_first():
    df = pd.DataFrame({"A": ["x"], "B": [1]})
    out = html_table(df, num_cols=("B",), total_row={"A": "Total", "B": "1"})
    assert out.index("Total") < out.index(">x<")


def test_money_mm_shows_millions_in_chilean_style():
    from ui.components import money_mm
    assert money_mm(1_616_968_617) == "$1,617 MM"
    assert money_mm(205_922_095_967) == "$205,922 MM"
    assert money_mm(float("nan")) == "—"


def test_html_table_total_row_can_go_last():
    df = pd.DataFrame({"A": ["x"], "B": [1]})
    out = html_table(df, num_cols=("B",), total_row={"A": "Total", "B": "1"}, total_position="bottom")
    assert out.index(">x<") < out.index("Total")


def test_money_cad_in_millions():
    assert money(3_310_000, "CAD") == "CA$3.31 MM"


def test_money_puts_the_minus_sign_before_the_currency_symbol():
    assert money(-2462394, "CLP") == "-$2,462,394"
    assert money(-3_310_000, "USD") == "-US$3.31 MM"
