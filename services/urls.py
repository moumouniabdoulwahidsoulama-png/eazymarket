from django.urls import path

from . import views

urlpatterns = [
    path("", views.services_home, name="services_home"),
    path("artisans/", views.artisan_list, name="artisan_list"),
    path("artisans/<slug:category_slug>/", views.artisan_list, name="artisan_list_category"),
    path("artisan/<int:artisan_id>/", views.artisan_detail, name="artisan_detail"),
    path("artisan/<int:artisan_id>/demande/", views.request_service, name="request_service"),
    path("artisan/<int:artisan_id>/avis/", views.leave_review, name="leave_review"),
    path("artisan/<int:artisan_id>/contact/", views.unlock_contact, name="unlock_contact"),
    path("avis/<int:review_id>/repondre/", views.reply_review, name="reply_review"),
    # Demandes & devis
    path("mes-demandes/", views.my_service_requests, name="my_service_requests"),
    path("demande/<int:request_id>/", views.service_request_detail, name="service_request_detail"),
    path("demande/<int:request_id>/message/", views.post_message, name="post_service_message"),
    path("demande/<int:request_id>/devis/", views.create_quote, name="create_quote"),
    path("demande/<int:request_id>/gerer/", views.manage_service_request, name="manage_service_request"),
    path("devis/<int:quote_id>/<str:action>/", views.respond_quote, name="respond_quote"),
    # Espace pro
    path("mon-atelier/", views.artisan_dashboard, name="artisan_dashboard"),
    path("devenir-artisan/", views.register_artisan, name="register_artisan"),
    path("mon-atelier/realisation/", views.add_portfolio, name="add_portfolio"),
    path("mon-atelier/disponibilite/", views.toggle_availability, name="toggle_availability"),
    path("abonnement/", views.subscribe_artisan, name="subscribe_artisan"),
    path("mise-en-avant/", views.boost_artisan, name="boost_artisan"),
]
