"""Ordine d'arrivo di una gara, condiviso dalla pagina dei risultati del gioco e
da quella pubblica dei risultati F1 (#134)."""


def race_classification(race):
    """Le righe di RaceResult della gara in ordine d'arrivo, con position_delta:
    posizioni guadagnate (positivo) o perse rispetto alla griglia, None se manca
    la posizione o la griglia."""
    results = list(
        race.entries.select_related("driver", "driver__team").order_by(
            "position", "driver__team__name", "driver__first_name", "driver__last_name"
        )
    )
    for entry in results:
        if entry.starting_grid is not None and entry.position is not None:
            entry.position_delta = entry.starting_grid - entry.position
        else:
            entry.position_delta = None
    return results
