"""La paleta (inspirada en Scotiabank) debe cumplir contraste WCAG: texto 4.5:1, gráficos 3:1."""
import pytest

from ui import theme


def luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


WHITE = "#FFFFFF"


@pytest.mark.parametrize("fg,bg", [
    ("TEXT", "CARD"), ("TEXT", "BG"), ("MUTED", "CARD"), ("MUTED", "BG"),
    ("ACCENT_DEEP", "CARD"), ("ON_SIDEBAR", "SIDEBAR"),
])
def test_text_pairs_meet_wcag_aa(fg, bg):
    assert contrast(getattr(theme, fg), getattr(theme, bg)) >= 4.5


def test_chart_colors_are_visible_on_white_surfaces():
    for color in [theme.ACCENT, theme.SERIE_1, theme.SERIE_2, *theme.PALETTE]:
        assert contrast(color, theme.CARD) >= 3.0, color


def test_brand_red_is_the_accent_and_sidebar_is_neutral():
    r, g, b = (int(theme.ACCENT[i:i + 2], 16) for i in (1, 3, 5))
    assert r > 200 and g < 40 and b < 40
    sr, sg, sb = (int(theme.SIDEBAR[i:i + 2], 16) for i in (1, 3, 5))
    assert max(sr, sg, sb) - min(sr, sg, sb) <= 12 and min(sr, sg, sb) > 230  # gris muy claro, sin color


def test_serif_display_stack_avoids_oldstyle_figures_font():
    assert "Georgia" not in theme.DISPLAY  # Georgia usa cifras de estilo antiguo: mal para montos


def test_palette_has_distinct_series_colors():
    assert len(set(theme.PALETTE)) == len(theme.PALETTE) >= 6


def test_chart_palette_priority_is_red_blue_gray_black_then_the_rest():
    assert theme.PALETTE[:4] == [theme.ACCENT, theme.SERIE_2, theme.GRIS, theme.NEGRO]
