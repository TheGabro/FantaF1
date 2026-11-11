from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def decimals(value):
    """
    Numero con al massimo due decimali, senza zeri inutili e con la virgola
    della pagina: 33,8 · 12 · ×1,25 (#270).

    I punti del GP sono float (punti F1 × moltiplicatore): 26 × 1,3 dà
    33,800000000000004. Si arrotonda alla seconda cifra invece di troncare,
    così un 33,8 salvato come 33,7999… resta 33,8 e non diventa 33,79.
    """
    if value is None or value == "":
        return ""  # come floatformat: niente «None» nella pagina
    try:
        number = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return value
    places = max(0, -number.normalize().as_tuple().exponent)
    return floatformat(number, places)
