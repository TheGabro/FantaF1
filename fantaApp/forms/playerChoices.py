from django import forms
from ..models import Driver

class SprintQualifyingForm(forms.Form):
    driver_sq1 = forms.ModelChoiceField(
        queryset=Driver.objects.none(),
        label="SQ1 – eliminato",
        empty_label="-- scegli pilota che verrà eliminato in SQ1 --",
        required=False,
    )
    driver_sq2 = forms.ModelChoiceField(
        queryset=Driver.objects.none(),
        label="SQ2 – eliminato",
        empty_label="-- scegli pilota che verrà eliminato in SQ2 --",
        required=False,
    )
    driver_sq3 = forms.ModelChoiceField(
        queryset=Driver.objects.none(),
        label="SQ3 – posizione 6-10",
        empty_label="-- scegli pilota che terminerù in P6-P10 in SQ3 --",
        required=False,
    )

    def __init__(self, *args, drivers_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if drivers_queryset is not None:
            # Imposta lo stesso queryset per tutti e tre i campi
            for field in ("driver_sq1", "driver_sq2", "driver_sq3"):
                self.fields[field].queryset = drivers_queryset

    def clean(self):
        cleaned = super().clean()
        selections = [
            cleaned.get("driver_sq1"),
            cleaned.get("driver_sq2"),
            cleaned.get("driver_sq3"),
        ]
        # filtra None
        chosen = [d for d in selections if d]
        if len(chosen) != len(set(chosen)):
            raise forms.ValidationError(
                "Non puoi selezionare lo stesso pilota in più slot."
            )
        return cleaned