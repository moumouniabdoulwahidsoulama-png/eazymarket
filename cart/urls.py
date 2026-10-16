from django.urls import path

from . import views

urlpatterns = [
    path("", views.cart_view, name="cart"),
    path("ajouter/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("retirer/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("modifier/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),
    path("vider/", views.clear_cart, name="clear_cart"),
    path("compter/", views.cart_count, name="cart_count"),
]
