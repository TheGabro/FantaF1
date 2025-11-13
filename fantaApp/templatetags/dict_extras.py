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
    except (KeyError, TypeError):
        return None