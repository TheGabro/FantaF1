from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import translation

from ..models import CustomUser


class PersonalDataForm(forms.ModelForm):
    """Account → Dati personali (#97). L'email resta fuori: per cambiarla serve
    la conferma via email (#105)."""

    class Meta:
        model = CustomUser
        fields = ["username", "first_name", "last_name"]
        labels = {"username": "Username", "first_name": "Nome", "last_name": "Cognome"}
        help_texts = {
            "username": "Lo usi per accedere ed è il nome di partenza quando ti iscrivi "
            "a un nuovo campionato. I nomi giocatore che hai già scelto nei "
            "campionati non cambiano.",
            "first_name": "Facoltativo, come il cognome: compaiono solo nella "
            "panoramica del tuo account.",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "first_name"):
            self.fields[name].widget.attrs["aria-describedby"] = f"id_{name}_help"

    def clean_username(self):
        username = self.cleaned_data.get("username")
        taken = (
            CustomUser.objects.filter(username=username)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if taken:
            raise ValidationError("Questo username è già in uso.")
        return username


class ChangePasswordForm(PasswordChangeForm):
    """Account → Sicurezza (#98): il PasswordChangeForm di Django con testi in
    italiano. Le regole della password le mostra il template (password_rules)."""

    error_messages = {
        "password_mismatch": "Le due password non corrispondono.",
        "password_incorrect": "La password attuale non è corretta.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Password attuale"
        self.fields["new_password1"].label = "Nuova password"
        self.fields["new_password1"].help_text = ""
        self.fields["new_password1"].widget.attrs[
            "aria-describedby"
        ] = "id_new_password1_help"
        self.fields["new_password2"].label = "Ripeti la nuova password"

    def clean_new_password2(self):
        # I messaggi dei validatori sono tradotti appena creati: come
        # all'iscrizione (#94) si forza l'italiano.
        with translation.override("it"):
            return super().clean_new_password2()
