from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def nav_section(context):
    """Sezione del sito della pagina aperta, per evidenziarla nel menu (#93).

    È il primo pezzo del percorso: "" per la home, "game", "championships",
    "account"… Le pagine nuove di una sezione si accendono da sole, senza
    elencarle qui.
    """
    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    if match is None:
        return None
    return match.route.split("/", 1)[0]
