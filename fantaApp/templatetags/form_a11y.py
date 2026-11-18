from django import template
from django.utils.html import format_html, format_html_join

register = template.Library()


def _error_id(field):
    return f"{field.auto_id}_error"


@register.filter
def linked_to_errors(field):
    """
    Il campo del form, collegato ai suoi errori quando ne ha (#292).

    Django 4.2 non lo fa da solo: sul campo con errori mette aria-invalid e
    aggiunge l'id della lista d'errore ad aria-describedby, dopo quello del
    testo d'aiuto se c'è già. Così chi usa un lettore di schermo, tornando sul
    campo, sente perché è sbagliato. Va in coppia con errors_with_id.
    """
    if not field.errors:
        return field.as_widget()
    described_by = field.field.widget.attrs.get("aria-describedby", "").split()
    described_by.append(_error_id(field))
    return field.as_widget(
        attrs={"aria-invalid": "true", "aria-describedby": " ".join(described_by)}
    )


@register.filter
def errors_with_id(field):
    """La lista d'errore del campo, come {{ field.errors }} ma con l'id a cui
    punta linked_to_errors; niente se il campo non ha errori."""
    if not field.errors:
        return ""
    return format_html(
        '<ul id="{}" class="errorlist">{}</ul>',
        _error_id(field),
        format_html_join("", "<li>{}</li>", ((error,) for error in field.errors)),
    )
