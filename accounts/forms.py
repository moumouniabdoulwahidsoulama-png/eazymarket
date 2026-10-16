"""Formulaires d'inscription et de profil."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from regions.models import Country

from .models import UserProfile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Adresse e-mail")
    first_name = forms.CharField(max_length=60, required=False, label="Prénom")
    last_name = forms.CharField(max_length=60, required=False, label="Nom")
    user_type = forms.ChoiceField(
        choices=UserProfile.Type.choices,
        widget=forms.RadioSelect,
        initial=UserProfile.Type.BUYER,
        label="Je m'inscris en tant que",
    )
    phone = forms.CharField(max_length=20, required=True, label="Téléphone")
    country = forms.ModelChoiceField(
        queryset=Country.objects.filter(is_active=True), required=False,
        label="Pays", empty_label=None,
    )
    quartier = forms.CharField(max_length=100, required=False, label="Quartier")
    city = forms.CharField(max_length=100, required=False, label="Ville")
    address = forms.CharField(widget=forms.Textarea, required=False, label="Adresse / repère")

    store_name = forms.CharField(max_length=100, required=False, label="Nom de la boutique")
    store_description = forms.CharField(widget=forms.Textarea, required=False, label="Que vendez-vous ?")

    vehicle_type = forms.ChoiceField(
        choices=[("", "Choisir…")] + list(UserProfile.VEHICLES), required=False, label="Véhicule"
    )
    delivery_zone = forms.CharField(max_length=100, required=False, label="Zone de livraison")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        initial_country = kwargs.pop("initial_country", None)
        super().__init__(*args, **kwargs)
        active = Country.objects.filter(is_active=True)
        self.fields["country"].queryset = active
        self.fields["country"].initial = initial_country or Country.default()
        if active.count() <= 1:
            self.fields["country"].widget = forms.HiddenInput()
        default = initial_country or Country.default()
        if default:
            self.fields["city"].initial = default.main_city

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("user_type")

        if role == UserProfile.Type.SELLER and not cleaned.get("store_name"):
            self.add_error("store_name", "Le nom de la boutique est obligatoire.")
        if role == UserProfile.Type.DELIVERY:
            if not cleaned.get("vehicle_type"):
                self.add_error("vehicle_type", "Indiquez votre moyen de transport.")
            if not cleaned.get("delivery_zone"):
                self.add_error("delivery_zone", "Indiquez votre zone de livraison.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        data = self.cleaned_data
        user.email = data["email"]
        user.first_name = data.get("first_name", "")
        user.last_name = data.get("last_name", "")
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.user_type = data["user_type"]
        profile.phone = data.get("phone", "")
        profile.address = data.get("address", "")
        profile.quartier = data.get("quartier", "")
        profile.country = data.get("country") or Country.default()
        profile.city = data.get("city") or (profile.country.main_city if profile.country else "")

        if data["user_type"] == UserProfile.Type.SELLER:
            profile.store_name = data.get("store_name", "")
            profile.store_description = data.get("store_description", "")
            # La boutique reste fermée jusqu'au règlement du pack : c'est le
            # paiement qui l'ouvre (voir payments.services._add_shop_slots).
            profile.is_store_active = False
        elif data["user_type"] == UserProfile.Type.DELIVERY:
            profile.vehicle_type = data.get("vehicle_type", "")
            profile.delivery_zone = data.get("delivery_zone", "")
            profile.is_available = True

        profile.save()
        # Le signal d'inscription avait mis en cache un profil « acheteur » :
        # on remplace ce cache, sinon la vue lit encore l'ancien rôle.
        user._state.fields_cache["profile"] = profile
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=60, required=False, label="Prénom")
    last_name = forms.CharField(max_length=60, required=False, label="Nom")
    email = forms.EmailField(required=False, label="Adresse e-mail")

    class Meta:
        model = UserProfile
        fields = [
            "phone", "whatsapp", "address", "country", "quartier", "city", "profile_picture",
            "store_name", "store_description", "store_logo",
            "vehicle_type", "delivery_zone",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            user = self.instance.user
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data.get("first_name", user.first_name)
        user.last_name = self.cleaned_data.get("last_name", user.last_name)
        if self.cleaned_data.get("email"):
            user.email = self.cleaned_data["email"]
        user.save()
        if commit:
            profile.save()
        return profile


class ProductForm(forms.Form):
    """Publication d'un produit par un vendeur."""

    name = forms.CharField(max_length=200, label="Nom du produit")
    category = forms.IntegerField(widget=forms.HiddenInput, required=False)
    base_price = forms.IntegerField(min_value=100, label="Votre prix (FCFA)")
    stock = forms.IntegerField(min_value=0, initial=1, label="Quantité disponible")
    description = forms.CharField(widget=forms.Textarea, label="Description")
