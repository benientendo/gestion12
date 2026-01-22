from django import forms
import requests
import json
from django.conf import settings
from django.contrib.auth.models import User
from .models import Article, Categorie, Vente, Client, Commercant, Boutique




class CategorieForm(forms.ModelForm):
    """Formulaire de catégorie original - déprécié, utiliser CategorieFormBoutique."""
    class Meta:
        model = Categorie
        fields = ['nom', 'description']  # Exclure le champ boutique car il sera assigné automatiquement
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ArticleForm(forms.ModelForm):
    """Formulaire d'article original - déprécié, utiliser ArticleFormBoutique."""
    code_recherche = forms.CharField(
        label='Rechercher un article par code', 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Entrez le code de l\'article',
            'class': 'form-control',
            'id': 'code-recherche'
        })
    )

    class Meta:
        model = Article
        fields = ['code', 'nom', 'description', 'devise', 'prix_vente', 'prix_vente_usd', 'prix_achat', 'prix_achat_usd', 'categorie', 'quantite_stock', 'image', 'est_actif']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code-barres ou code unique'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de l\'article'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description de l\'article'}),
            'devise': forms.Select(attrs={'class': 'form-select'}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix de vente'}),
            'prix_vente_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix de vente en USD (optionnel)'}),
            'prix_achat': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix d\'achat'}),
            'prix_achat_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix d\'achat en USD (optionnel)'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'quantite_stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantité en stock'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if 'categorie' in self.fields:
            self.fields['categorie'].required = False
        # En mode modification, ne pas exiger le champ code (on ne l'édite plus dans certains formulaires)
        if instance is not None and getattr(instance, 'pk', None) and 'code' in self.fields:
            self.fields['code'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Définir prix_achat à 0 par défaut s'il n'est pas fourni
        if not hasattr(instance, 'prix_achat') or instance.prix_achat is None:
            instance.prix_achat = 0
        if commit:
            instance.save()
        return instance

    def rechercher_article_par_code(self, code):
        """
        Recherche un article via l'API en utilisant son code
        
        :param code: Code de l'article à rechercher
        :return: Dictionnaire avec les détails de l'article ou None
        """
        try:
            # Construire l'URL de l'API
            base_url = settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'
            url = f'{base_url}/api/articles/par_code/'
            
            # Faire la requête
            # Envoyer l'objet complet du code QR
            full_code_data = {
                'id': None,  # Peut être None si non disponible
                'code': code,
                'nom': None,
                'prix': None,
                'categorie': None
            }
            response = requests.get(url, params={'code': json.dumps(full_code_data)}, timeout=5)
            
            # Vérifier la réponse
            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
            return response.json()
        
        except requests.exceptions.HTTPError as http_err:
            print(f'Erreur HTTP lors de la recherche de l\'article : {http_err}')
            return None
        except requests.exceptions.ConnectionError as conn_err:
            print(f'Erreur de connexion : {conn_err}')
            return None
        except requests.exceptions.Timeout as timeout_err:
            print(f'Délai de requête dépassé : {timeout_err}')
            return None
        except requests.exceptions.RequestException as req_err:
            print(f'Erreur lors de la requête : {req_err}')
            return None
        except json.JSONDecodeError as json_err:
            print(f'Erreur de décodage JSON : {json_err}')
            return None
        except Exception as e:
            print(f'Erreur inattendue lors de la recherche de l\'article : {e}')
            return None


# ===== FORMULAIRES POUR LA STRUCTURE MULTI-COMMERÇANTS =====

# Formulaires supprimés - retour à l'état original


class ClientForm(forms.ModelForm):
    """Formulaire pour créer/modifier un client MAUI."""
    
    class Meta:
        model = Client
        fields = ['nom_terminal', 'description', 'numero_serie', 'notes', 'est_actif']
        widgets = {
            'nom_terminal': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_numero_serie(self):
        numero_serie = self.cleaned_data['numero_serie']
        if self.instance and self.instance.pk:
            # Mode modification - vérifier que le numéro de série n'est pas déjà pris par un autre client
            if Client.objects.filter(numero_serie=numero_serie).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Ce numéro de série est déjà utilisé.")
        else:
            # Mode création - vérifier que le numéro de série n'existe pas
            if Client.objects.filter(numero_serie=numero_serie).exists():
                raise forms.ValidationError("Ce numéro de série est déjà utilisé.")
        return numero_serie


class CommercantForm(forms.ModelForm):
    """Formulaire pour créer/modifier un commerçant."""
    
    # Champs supplémentaires pour la création de l'utilisateur Django
    username = forms.CharField(
        max_length=150,
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Nom d'utilisateur pour se connecter au système"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Mot de passe",
        help_text="Mot de passe pour se connecter au système"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirmer le mot de passe"
    )
    prenom = forms.CharField(
        max_length=30,
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    nom = forms.CharField(
        max_length=30,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Commercant
        fields = [
            'nom_entreprise', 'nom_responsable', 'email', 'telephone', 'adresse',
            'numero_registre_commerce', 'numero_fiscal', 'type_abonnement',
            'max_boutiques', 'est_actif', 'notes_admin'
        ]
        widgets = {
            'nom_entreprise': forms.TextInput(attrs={'class': 'form-control'}),
            'nom_responsable': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'numero_registre_commerce': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_fiscal': forms.TextInput(attrs={'class': 'form-control'}),
            'type_abonnement': forms.Select(attrs={'class': 'form-control'}),
            'max_boutiques': forms.NumberInput(attrs={'class': 'form-control'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes_admin': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'numero_registre_commerce': 'RCCM',
            'numero_fiscal': 'Id. Nat',
        }
    
    def __init__(self, *args, **kwargs):
        # Si on modifie un commerçant existant, ne pas afficher les champs utilisateur
        self.is_editing = kwargs.get('instance') is not None
        super().__init__(*args, **kwargs)
        
        if self.is_editing:
            # En mode modification, supprimer les champs utilisateur
            del self.fields['username']
            del self.fields['password']
            del self.fields['confirm_password']
            del self.fields['prenom']
            del self.fields['nom']
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.is_editing:
            # Validation uniquement en mode création
            password = cleaned_data.get('password')
            confirm_password = cleaned_data.get('confirm_password')
            
            if password and confirm_password and password != confirm_password:
                raise forms.ValidationError("Les mots de passe ne correspondent pas.")
            
            # Vérifier que le nom d'utilisateur n'existe pas déjà
            username = cleaned_data.get('username')
            if username and User.objects.filter(username=username).exists():
                raise forms.ValidationError("Ce nom d'utilisateur existe déjà.")
        
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if self.instance and self.instance.pk:
            # Mode modification - vérifier que l'email n'est pas déjà pris par un autre commerçant
            if Commercant.objects.filter(email=email).exclude(id=self.instance.id).exists():
                raise forms.ValidationError("Cet email est déjà utilisé par un autre commerçant.")
        else:
            # Mode création - vérifier que l'email n'existe pas
            if Commercant.objects.filter(email=email).exists():
                raise forms.ValidationError("Cet email est déjà utilisé.")
        return email


class BoutiqueForm(forms.ModelForm):
    """Formulaire pour créer/modifier une boutique."""
    
    class Meta:
        model = Boutique
        fields = [
            'nom', 'description', 'type_commerce', 'adresse', 'ville', 
            'code_postal', 'telephone', 'email'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'type_commerce': forms.Select(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'code_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nom': 'Nom de la boutique',
            'description': 'Description',
            'type_commerce': 'Type de commerce',
            'adresse': 'Adresse complète',
            'ville': 'Ville',
            'code_postal': 'Code postal',
            'telephone': 'Téléphone',
            'email': 'Email de contact',
        }
