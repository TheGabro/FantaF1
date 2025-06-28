from django import forms
from .models import CustomUser

class CustomUserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = CustomUser.Role.USER  # imposta come utente base
        if commit:
            user.save()
        return user