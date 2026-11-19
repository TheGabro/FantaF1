from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_static(context, path):
    """Indirizzo completo di un file statico (#295): l'anteprima di WhatsApp e dei
    social vuole l'immagine con dominio e schema, non il solo percorso."""
    url = static(path)
    request = context.get("request")
    return request.build_absolute_uri(url) if request else url


@register.simple_tag(takes_context=True)
def canonical_url(context):
    """Indirizzo completo della pagina senza query string (#295): og:url non deve
    ripetere parametri come ?next= o ?from=, che possono arrivare da fuori."""
    request = context.get("request")
    return request.build_absolute_uri(request.path) if request else ""
