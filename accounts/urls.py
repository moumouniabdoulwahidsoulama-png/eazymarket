from django.urls import path

from . import views

urlpatterns = [
    path("inscription/", views.register, name="register"),
    path("connexion/", views.login_view, name="login"),
    path("connexion/code/", views.login_verify_view, name="login_verify"),
    path("securite/", views.security_settings, name="security_settings"),
    path("deconnexion/", views.logout_view, name="logout"),
    path("profil/", views.profile, name="profile"),
    # Ajouter une activité à un compte existant
    path("devenir-vendeur/", views.become_seller, name="become_seller"),
    path("devenir-livreur/", views.become_delivery, name="become_delivery"),
    # Vendeur
    path("vendeur/", views.seller_dashboard, name="seller_dashboard"),
    path("vendeur/produit/", views.add_product, name="add_product"),
    path("vendeur/emplacements/", views.buy_slots, name="buy_slots"),
    path("vendeur/produit/<int:product_id>/supprimer/", views.delete_product, name="delete_product"),
    path("vendeur/produit/<int:product_id>/visibilite/", views.toggle_product, name="toggle_product"),
    path("vendeur/produit/<int:product_id>/modifier/", views.update_product, name="update_product"),
    # Livreur
    path("livreur/", views.delivery_dashboard, name="delivery_dashboard"),
    path("livreur/disponibilite/", views.toggle_delivery_status, name="toggle_delivery_status"),
    path("livreur/accepter/<int:order_id>/", views.accept_delivery, name="accept_delivery"),
    # Administration
    path("pilotage/", views.admin_dashboard, name="admin_dashboard"),
]
