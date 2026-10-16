from django.contrib import admin

from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "source", "duree_affichee", "poids_affiche",
                    "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("title", "owner__username", "external_url")
    list_editable = ("is_approved",)
    readonly_fields = ("duration", "size", "created_at")
    actions = ("retirer", "valider")

    @admin.display(description="Source")
    def source(self, obj):
        return "Fichier" if obj.is_hosted else (obj.plateforme_nom or "Lien")

    @admin.display(description="Durée")
    def duree_affichee(self, obj):
        return obj.duree_affichee or "—"

    @admin.display(description="Poids")
    def poids_affiche(self, obj):
        return obj.poids_affiche or "—"

    @admin.action(description="Retirer du site")
    def retirer(self, request, queryset):
        n = queryset.update(is_approved=False)
        self.message_user(request, f"{n} vidéo(s) retirée(s) du site.")

    @admin.action(description="Remettre en ligne")
    def valider(self, request, queryset):
        n = queryset.update(is_approved=True)
        self.message_user(request, f"{n} vidéo(s) remise(s) en ligne.")
