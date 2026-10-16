from django.urls import path

from . import views

urlpatterns = [
    path("ajouter/", views.add_video, name="add_video"),
    path("<int:video_id>/supprimer/", views.delete_video, name="delete_video"),
    path("emplacements/", views.buy_video_slots, name="buy_video_slots"),
]
