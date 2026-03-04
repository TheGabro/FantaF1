from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Restituisce dictionary[key] nel template.
    Se la chiave non c’è, torna None.
    """
    try:
        return dictionary[key]
    except (KeyError, TypeError, IndexError):
        return None


@register.filter
def to_range(value):
    """
    Serve a creare un range da 0 a value-1 nel template, utile per i loop.
    Se value non è un intero, torna un range vuoto.
    """
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)