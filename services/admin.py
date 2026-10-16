from django.contrib import admin

from .models import (
    Artisan, ContactUnlock, Portfolio, Quote, ServiceCategory, ServiceMessage,
    ServiceRequest, ServiceReview,
)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "order")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order",)


class PortfolioInline(admin.TabularInline):
    model = Portfolio
    extra = 0


@admin.register(Artisan)
class ArtisanAdmin(admin.ModelAdmin):
    list_display = ("full_name", "service_category", "quartier", "subscription_active",
                    "subscription_end", "is_verified", "contact_views", "rating", "is_blocked")
    list_filter = ("plan", "subscription_active", "is_verified", "is_blocked", "service_category")
    search_fields = ("full_name", "phone", "user__username", "quartier")
    list_editable = ("is_verified", "is_blocked")
    inlines = (PortfolioInline,)
    filter_horizontal = ("secondary_categories",)


class QuoteInline(admin.TabularInline):
    model = Quote
    extra = 0


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "title", "client", "artisan", "status", "urgency", "created_at")
    list_filter = ("status", "urgency")
    search_fields = ("reference", "title", "client__username", "artisan__full_name")
    inlines = (QuoteInline,)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("reference", "artisan", "total", "status", "created_at")
    list_filter = ("status",)


@admin.register(ServiceReview)
class ServiceReviewAdmin(admin.ModelAdmin):
    list_display = ("artisan", "client", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(ContactUnlock)
class ContactUnlockAdmin(admin.ModelAdmin):
    list_display = ("client", "artisan", "amount", "is_free", "created_at", "expires_at")
    list_filter = ("is_free",)
    search_fields = ("client__username", "artisan__full_name", "transaction_reference")


admin.site.register(ServiceMessage)
