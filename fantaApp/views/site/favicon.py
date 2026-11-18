from django.shortcuts import redirect
from django.templatetags.static import static


def favicon(request):
    """/favicon.ico (#296): browser, lettori di feed e strumenti la cercano nella
    radice anche se la pagina indica le sue icone. Rimanda al file statico; il redirect
    è temporaneo perché in produzione il nome del file contiene l'hash del contenuto."""
    return redirect(static("fantaApp/img/favicon.ico"))
