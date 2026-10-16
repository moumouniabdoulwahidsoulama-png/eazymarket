from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "phone", "country", "city", "is_verified",
                    "store_name", "unlimited_slots", "is_official")
    list_filter = ("user_type", "country", "is_verified", "is_store_active", "unlimited_slots")
    search_fields = ("user__username", "user__email", "phone", "store_name")
    list_editable = ("is_verified", "unlimited_slots", "is_official")
    list_select_related = ("user", "country")


from .models import LogConnexion


@admin.register(LogConnexion)
class LogConnexionAdmin(admin.ModelAdmin):
    list_display = ("date", "succes", "identifiant_saisi", "utilisateur", "adresse_ip")
    list_filter = ("succes", "date")
    search_fields = ("identifiant_saisi", "adresse_ip", "utilisateur__username")
    readonly_fields = ("utilisateur", "identifiant_saisi", "adresse_ip",
                       "user_agent", "succes", "date")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False  # un journal ne se remplit pas à la main
