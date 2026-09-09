from django import forms
from ..models import CustomUser, Championship, League, ChampionshipPlayer
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from datetime import datetime

CURRENT_YEAR = datetime.now().year

class CustomUserRegistrationForm(forms.ModelForm):

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label="Ripeti la password",
        widget=forms.PasswordInput
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise ValidationError("Questo username è già in uso.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Questa email è già registrata.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError("Le due password non corrispondono.")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.user_type = CustomUser.UserType.USER  # imposta come utente base
        if commit:
            user.save()
        return user
    

class UsernameOrEmailAuthenticationForm(forms.Form):
    identifier = forms.CharField(label="Username o Email")
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get("identifier")
        password = cleaned_data.get("password")


        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(email=identifier)
        except UserModel.DoesNotExist:
            try:
                user = UserModel.objects.get(username=identifier)
            except UserModel.DoesNotExist:
                raise ValidationError("Utente non trovato con questo username o email.")

        self.user = authenticate(username=user.username, password=password)
        if self.user is None:
            raise ValidationError("Password errata.")

        return cleaned_data

    def get_user(self):
        return self.user
    

class ChampionshipForm(forms.ModelForm):

    year = forms.IntegerField(widget=forms.HiddenInput(), initial=CURRENT_YEAR)

    join_as_player = forms.BooleanField(
        label="Partecipo anch'io come giocatore",
        required=False,
        initial=True,
    )
    player_name = forms.CharField(
        label="Il tuo nome giocatore",
        max_length=50,
        required=False,
    )
    # Le leghe nascono nella stessa richiesta: al render non esistono ancora e
    # una tendina legata al database è impossibile. Si sceglie per posizione e
    # le opzioni le popola il JavaScript dai nomi lega digitati; la view valida
    # l'indice contro le leghe davvero create.
    player_league_index = forms.IntegerField(
        label="La tua lega",
        required=False,
        min_value=0,
        widget=forms.Select(choices=[]),
    )

    class Meta:
        model = Championship
        fields = ['name', 'year']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['player_name'].initial = user.username

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        year = cleaned_data.get('year')
        if Championship.objects.filter(name=name, year=year).exists():
            raise ValidationError("Questo nome per il campionato è già in uso quest'anno")

        # Nome giocatore lasciato vuoto: si usa lo username. Il campionato è
        # appena nato, quindi nessun altro nome può ancora essere occupato.
        if cleaned_data.get('join_as_player') and not cleaned_data.get('player_name'):
            if self.user is None:
                raise ValidationError("Indica il nome con cui vuoi giocare.")
            cleaned_data['player_name'] = self.user.username

        return cleaned_data


class LeagueForm(forms.ModelForm):
    class Meta:
        model = League
        fields = ['name']

LeagueFormSet = inlineformset_factory(
    Championship,
    League,
    form=LeagueForm,
    # extra=2,  # default: due leghe (F1 e DFA)
    can_delete=False
)


class ChampionshipPlayerForm(forms.ModelForm):
    """Iscrizione a un campionato esistente.

    Il campionato non è un campo del form: lo fissa la view leggendolo dall'URL.
    Esporlo come tendina permetteva di iscriversi a un campionato diverso da
    quello aperto, e di scegliere una lega appartenente a un altro campionato.
    """

    class Meta:
        model = ChampionshipPlayer
        fields = ['player_name', 'league']
        labels = {
            'player_name': "Il tuo nome giocatore",
            'league': "Lega",
        }

    def __init__(self, *args, championship=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.championship = championship
        # Va messo sull'istanza subito: la validazione del ModelForm chiama
        # ChampionshipPlayer.clean(), che legge self.championship e senza questo
        # solleva RelatedObjectDoesNotExist invece di validare.
        self.instance.championship = championship

        leagues = (
            League.objects.filter(championship=championship).order_by('id')
            if championship is not None
            else League.objects.none()
        )
        self.fields['league'].queryset = leagues
        self.fields['league'].empty_label = None
        # Con una lega sola non c'è niente da scegliere: si preseleziona.
        if len(leagues) == 1:
            self.fields['league'].initial = leagues[0]

    def clean_player_name(self):
        player_name = self.cleaned_data['player_name']
        if self.championship is not None and ChampionshipPlayer.objects.filter(
            championship=self.championship,
            player_name=player_name,
        ).exists():
            raise ValidationError("Questo nome giocatore è già stato usato in questo campionato.")
        return player_name