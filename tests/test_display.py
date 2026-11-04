import pandas as pd

from wm.display import add_display_columns, advisor_names, synthetic_cliente


def test_synthetic_cliente_is_deterministic_and_typed():
    a1, a2 = synthetic_cliente("RUT_1"), synthetic_cliente("RUT_1")
    assert a1 == a2
    assert a1[1] in ("Persona natural", "Persona jurídica")
    kinds = {synthetic_cliente(f"RUT_{i}")[1] for i in range(60)}
    assert kinds == {"Persona natural", "Persona jurídica"}


def test_juridica_names_look_like_companies_and_natural_like_people():
    for i in range(80):
        nombre, tipo = synthetic_cliente(f"RUT_{i}")
        if tipo == "Persona jurídica":
            assert nombre.startswith("Dummy ") and nombre.split()[-1].rstrip(".") in ("Ltd", "Inc", "LLC")
        else:
            assert nombre.startswith("Dummy Client ") and len(nombre.split()) == 3


def test_advisor_names_are_unique_full_names_and_stable():
    codes = [f"IA_{i}" for i in range(40)]
    names = advisor_names(codes)
    assert len(set(names.values())) == 40
    assert all(n.startswith("Dummy Advisor ") and not n.startswith("IA_") for n in names.values())
    assert advisor_names(codes) == names


def test_add_display_columns_builds_rut_dot_name_label():
    df = pd.DataFrame({"rut": ["RUT_1", "RUT_2"], "advisor": ["IA_1", "IA_2"]})
    out = add_display_columns(df)
    assert out.loc[0, "cliente_label"] == f"RUT_1 {out.loc[0, 'nombre']}"
    assert set(out["tipo_persona"]) <= {"Persona natural", "Persona jurídica"}
    assert not out["advisor_nombre"].str.startswith("IA_").any()


def test_columns_from_excel_take_precedence_over_synthetic():
    df = pd.DataFrame({"rut": ["RUT_1"], "advisor": ["IA_1"], "nombre_cliente": ["Ana Real Pérez"],
                       "tipo_persona": ["Persona natural"], "nombre_advisor": ["Luis Gómez"]})
    out = add_display_columns(df)
    assert out.loc[0, "nombre"] == "Ana Real Pérez" and out.loc[0, "advisor_nombre"] == "Luis Gómez"
    assert out.loc[0, "cliente_label"] == "RUT_1 Ana Real Pérez"


def test_format_rut_puts_thousand_dots_and_verifier_digit():
    from wm.display import format_rut
    assert format_rut("RUT_01234567") == "123.456-7"
    assert format_rut("RUT_12345678K") == "12.345.678-K"
    assert format_rut("RUT_1") == "RUT_1"  # sin forma de RUT: se deja igual
