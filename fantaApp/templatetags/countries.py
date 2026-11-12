from django import template

register = template.Library()

# Paese del circuito come lo salva l'import (Circuit.country) -> codice ISO della
# bandiera in static/fantaApp/img/flags/ (flag-icons, licenza MIT) e nome in
# italiano (#132). Ci sono i paesi dei calendari 2025 e 2026, più i nomi lunghi
# che l'import potrebbe usare per gli stessi paesi. La Malesia ospita nel 2026
# il GP del Bahrein (#280).
COUNTRIES = {
    "Australia": ("au", "Australia"),
    "Austria": ("at", "Austria"),
    "Azerbaijan": ("az", "Azerbaigian"),
    "Bahrain": ("bh", "Bahrein"),
    "Belgium": ("be", "Belgio"),
    "Brazil": ("br", "Brasile"),
    "Canada": ("ca", "Canada"),
    "China": ("cn", "Cina"),
    "Hungary": ("hu", "Ungheria"),
    "Italy": ("it", "Italia"),
    "Japan": ("jp", "Giappone"),
    "Malaysia": ("my", "Malesia"),
    "Mexico": ("mx", "Messico"),
    "Monaco": ("mc", "Monaco"),
    "Netherlands": ("nl", "Paesi Bassi"),
    "Qatar": ("qa", "Qatar"),
    "Saudi Arabia": ("sa", "Arabia Saudita"),
    "Singapore": ("sg", "Singapore"),
    "Spain": ("es", "Spagna"),
    "UAE": ("ae", "Emirati Arabi Uniti"),
    "United Arab Emirates": ("ae", "Emirati Arabi Uniti"),
    "UK": ("gb", "Regno Unito"),
    "United Kingdom": ("gb", "Regno Unito"),
    "Great Britain": ("gb", "Regno Unito"),
    "USA": ("us", "Stati Uniti"),
    "United States": ("us", "Stati Uniti"),
}


def country(name):
    """(codice della bandiera, nome in italiano); per un paese che non è in
    tabella (None, il nome dell'import)."""
    return COUNTRIES.get((name or "").strip(), (None, name))


@register.filter
def country_it(name):
    """Nome del paese in italiano: «UK» → «Regno Unito»."""
    return country(name)[1]


def grand_prix_country(weekend):
    """(codice, nome italiano) del paese del Gran Premio. Di solito è quello del
    circuito; se il nome del weekend comincia con un paese della tabella vale
    quello: il «Bahrain Grand Prix in Malaysia» del 2026 è il GP del Bahrein,
    anche se si corre a Sepang (#280)."""
    named = (weekend.event_name or "").split(" Grand Prix", 1)[0]
    if named in COUNTRIES:
        return COUNTRIES[named]
    return country(weekend.circuit.country)


@register.inclusion_tag("fantaApp/_weekend_flag.html")
def weekend_flag(weekend, size=""):
    """Bandiera del paese del Gran Premio al posto del badge «R1…R24» (#132).
    Per un paese senza bandiera resta il badge del round. size: "" (come il
    badge piccolo), "md", "lg", "xl"."""
    code, name = grand_prix_country(weekend)
    return {"weekend": weekend, "code": code, "name": name, "size": size}
