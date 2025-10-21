from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class UserCreateForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False, help_text='Optionnel')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optionnel')
    is_staff = forms.BooleanField(required=False, help_text='Désigne si l\'utilisateur peut se connecter au site d\'administration.')
    is_superuser = forms.BooleanField(required=False, help_text='Désigne que cet utilisateur a toutes les permissions sans les assigner explicitement.')

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_superuser')

class UserEditForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False, help_text='Optionnel')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optionnel')
    is_active = forms.BooleanField(required=False, help_text='Désigne si l\'utilisateur doit être traité comme actif.')
    is_staff = forms.BooleanField(required=False, help_text='Désigne si l\'utilisateur peut se connecter au site d\'administration.')
    is_superuser = forms.BooleanField(required=False, help_text='Désigne que cet utilisateur a toutes les permissions sans les assigner explicitement.')

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')
