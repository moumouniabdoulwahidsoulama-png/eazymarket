"""Table de routage principale d'EazyMarket."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

admin.site.site_header = "Administration EazyMarket"
admin.site.site_title = "EazyMarket"
admin.site.index_title = "Pilotage de la place de marché"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Raccourci : /admin/ mène à l'administration Django (habitude de tous les projets)
    path("admin/", RedirectView.as_view(url="/django-admin/", permanent=False)),
    path("compte/", include("accounts.urls")),
    path("panier/", include("cart.urls")),
    path("commandes/", include("orders.urls")),
    path("services/", include("services.urls")),
    path("paiement/", include("payments.urls")),
    path("livraison/", include("delivery.urls")),
    path("notifications/", include("notifications.urls")),
    path("infos/", include("pages.urls")),
    path("pays/", include("regions.urls")),
    path("videos/", include("videos.urls")),
    path("", include("products.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
elif settings.SERVE_MEDIA:
    # Les photos envoyées par les vendeurs et les artisans, quand le serveur
    # web ne les sert pas lui-même (cas courant sur cPanel/Passenger).
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
            name="media",
        )
    ]
