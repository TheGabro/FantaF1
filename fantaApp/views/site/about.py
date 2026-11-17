from django.shortcuts import render

from .privacy import CONTACT_EMAIL


def about(request):
    """Chi siamo (#108), aperta a tutti senza login. Testo della bozza approvata
    da Davide il 17/11/2026: la storia del gioco e il team con i soprannomi.
    Niente telefoni né moduli: si scrive all'email del sito."""
    return render(request, "fantaApp/site/about.html", {"contact_email": CONTACT_EMAIL})
