from django.urls import path

from . import views

urlpatterns = [
    path("validation/", views.checkout, name="checkout"),
    path("mes-commandes/", views.my_orders, name="my_orders"),
    path("vendeur/", views.seller_orders, name="seller_orders"),
    path("livreur/", views.delivery_orders, name="delivery_orders"),
    path("confirmation/<int:confirmation_id>/", views.respond_confirmation, name="respond_confirmation"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/message/", views.post_order_message, name="post_order_message"),
    path("<int:order_id>/annuler/", views.cancel_order, name="cancel_order"),
    path("<int:order_id>/recue/", views.confirmer_reception, name="confirmer_reception"),
    path("<int:order_id>/non-recu/", views.signaler_non_recu, name="signaler_non_recu"),
    path("<int:order_id>/remboursement/", views.demander_mon_remboursement,
         name="demander_mon_remboursement"),
    path("<int:order_id>/statut/", views.update_order_status, name="update_order_status"),
]
