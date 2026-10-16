from django.urls import path

from . import views

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("compter/", views.notification_count, name="notification_count"),
    path("lue/<int:notification_id>/", views.notification_mark_read, name="notification_mark_read"),
    path("supprimer/<int:notification_id>/", views.notification_delete, name="notification_delete"),
    path("tout-supprimer/", views.notification_clear_all, name="notification_clear_all"),
]
