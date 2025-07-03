from django import forms
from .models import CustomUser
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

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