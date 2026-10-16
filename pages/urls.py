from django.urls import path

from . import views

urlpatterns = [
    path("a-propos/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("faq/", views.faq, name="faq"),
    path("conditions/", views.terms, name="terms"),
    path("comment-ca-marche/", views.how_it_works, name="how_it_works"),
    path("vendre/", views.sell, name="sell"),
]
