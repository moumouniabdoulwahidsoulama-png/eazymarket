from django.urls import path

from . import views

urlpatterns = [
    path("<str:code>/", views.choose_country, name="choose_country"),
]
