import pandas as pd

from wm.auth import advisors_from, check_pin


def test_no_pin_required_allows_without_pin():
    assert check_pin("IA_1", None, {"pin_obligatorio": False, "pines": {}}) is True


def test_configured_pin_is_enforced_even_if_not_mandatory():
    cfg = {"pin_obligatorio": False, "pines": {"IA_1": "1234"}}
    assert check_pin("IA_1", None, cfg) is False
    assert check_pin("IA_1", "1234", cfg) is True
    assert check_pin("IA_2", None, cfg) is True


def test_mandatory_without_configured_pin_denies():
    assert check_pin("IA_1", "cualquiera", {"pin_obligatorio": True, "pines": {}}) is False


def test_wrong_pin_denied():
    assert check_pin("IA_1", "0000", {"pin_obligatorio": False, "pines": {"IA_1": "1234"}}) is False


def test_advisors_from_sorted_unique_nonnull():
    df = pd.DataFrame({"advisor": ["IA_2", "IA_1", "IA_2", None]})
    assert advisors_from(df) == ["IA_1", "IA_2"]


def test_can_edit_dato_rules():
    from wm.auth import can_edit_dato
    assert can_edit_dato(None, "IA_1", "Investment Advisor") is True       # aún sin valor
    assert can_edit_dato("IA_1", "IA_1", "Investment Advisor") is True     # el autor
    assert can_edit_dato("IA_2", "IA_1", "Investment Advisor") is False    # otro advisor
    assert can_edit_dato(None, "Managing Director", "Managing Director") is False  # MD solo lee


def _view():
    import pandas as pd
    return pd.DataFrame({"advisor": ["IA_1", "IA_2", "IA_1"], "advisor_nombre": ["Juan Rojas", "María Díaz", "Juan Rojas"]})


CFG = {"usuarios": {"md": {"nombre": "Managing Director", "rol": "Managing Director"},
                    "estrategia": {"nombre": "Equipo de Estrategia", "rol": "Estrategia"}},
       "roles": {"Investment Advisor": ["Client Portal", "Estrategia"], "Managing Director": ["Client Portal", "Estrategia"],
                 "Estrategia": ["Estrategia"]}}


def test_resolve_user_accepts_advisor_code_or_name_ignoring_case_and_accents():
    from wm.auth import resolve_user
    for text in ("IA_2", "ia_2", "maria diaz", " María Díaz "):
        u = resolve_user(text, _view(), CFG)
        assert u["advisor"] == "IA_2" and u["rol"] == "Investment Advisor"


def test_resolve_user_finds_configured_users_and_rejects_unknown():
    from wm.auth import resolve_user
    assert resolve_user("MD", _view(), CFG)["rol"] == "Managing Director"
    assert resolve_user("Equipo de Estrategia", _view(), CFG)["rol"] == "Estrategia"
    assert resolve_user("nadie", _view(), CFG) is None and resolve_user("", _view(), CFG) is None


def test_modules_depend_on_role():
    from wm.auth import modules_for
    assert modules_for("Investment Advisor", CFG) == ["Client Portal", "Estrategia"]
    assert modules_for("Managing Director", CFG) == ["Client Portal", "Estrategia"]
    assert modules_for("Estrategia", CFG) == ["Estrategia"]
    assert modules_for("Otro", CFG) == []


def test_check_login_uses_user_pin_then_default_then_legacy_pin():
    from wm.auth import check_login
    cfg = {"pin_por_defecto": "123"}
    assert check_login({"pin_key": "md", "pin": None}, "123", cfg, {}) is True
    assert check_login({"pin_key": "md", "pin": None}, "124", cfg, {}) is False
    assert check_login({"pin_key": "md", "pin": None}, None, cfg, {}) is False
    assert check_login({"pin_key": "x", "pin": "abc"}, "abc", cfg, {}) is True          # el pin propio manda
    assert check_login({"pin_key": "IA_1", "pin": None}, "9", {}, {"pines": {"IA_1": "9"}}) is True  # sin defecto: advisors.yaml


def test_generic_advisor_user_maps_to_first_advisor_and_md_to_none():
    from wm.auth import resolve_user
    cfg = {**CFG, "usuarios": {**CFG["usuarios"], "advisor": {"nombre": "Advisor", "rol": "Investment Advisor", "advisor": "primero"}}}
    u = resolve_user("advisor", _view(), cfg)
    assert u["advisor"] == "IA_1" and u["rol"] == "Investment Advisor" and u["pin_key"] == "advisor"
    assert resolve_user("md", _view(), cfg)["advisor"] is None
