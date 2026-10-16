from django.urls import path

from . import views

urlpatterns = [
    path("payer/<str:reference>/", views.pay, name="payment_pay"),
    path("declarer/<str:reference>/", views.declare, name="payment_declare"),
    path("retour/<str:reference>/", views.payment_return, name="payment_return"),
    path("statut/<str:reference>/", views.status, name="payment_status"),
    path("webhook/", views.webhook, name="payment_webhook"),
    # Portefeuille
    path("portefeuille/", views.wallet_view, name="wallet"),
    path("portefeuille/retrait/", views.wallet_withdraw, name="wallet_withdraw"),
    path("portefeuille/coordonnees/", views.wallet_settings, name="wallet_settings"),
    # Back-office
    path("admin/transactions/", views.admin_transactions, name="admin_transactions"),
    path("admin/transactions/<str:reference>/<str:action>/", views.admin_review, name="admin_review"),
    path("admin/retraits/", views.admin_payouts, name="admin_payouts"),
    path("admin/retraits/<str:reference>/payer/", views.admin_payout_paid, name="admin_payout_paid"),
]
