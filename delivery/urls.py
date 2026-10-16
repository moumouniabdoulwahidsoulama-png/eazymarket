from django.urls import path

from . import views

urlpatterns = [
    # Annuaire public — trouver un livreur
    path("livreurs/", views.driver_list, name="driver_list"),
    path("livreur/<int:profile_id>/", views.driver_detail, name="driver_detail"),

    path("mon-dossier/", views.referral_dashboard, name="referral_dashboard"),
    path("mon-dossier/repondant/", views.add_sponsor, name="add_sponsor"),
    path("mon-dossier/repondant/<int:sponsor_id>/retirer/", views.remove_sponsor, name="remove_sponsor"),
    path("mon-dossier/envoyer/", views.submit_referral, name="submit_referral"),
    path("dossiers/", views.referral_list, name="referral_list"),
    path("dossiers/<int:referral_id>/", views.verify_referral, name="verify_referral"),
]
