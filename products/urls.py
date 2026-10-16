from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("produits/", views.product_list, name="product_list"),
    path("recherche/", views.search, name="search"),
    path("favoris/", views.favorites, name="favorites"),
    path("categorie/<slug:slug>/", views.category_products, name="category_products"),
    path("boutique/<slug:slug>/", views.store_front, name="store_front"),
    path("produit/<slug:slug>/", views.product_detail, name="product_detail"),
    path("produit/<slug:slug>/avis/", views.add_review, name="add_product_review"),
    path("favori/<int:product_id>/", views.toggle_favorite, name="toggle_favorite"),
]
