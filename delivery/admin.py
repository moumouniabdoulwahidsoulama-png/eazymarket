from django.contrib import admin

from .models import DeliveryReferral, Sponsor


class SponsorInline(admin.TabularInline):
    model = Sponsor
    extra = 0


@admin.register(DeliveryReferral)
class DeliveryReferralAdmin(admin.ModelAdmin):
    list_display = ("deliverer", "referral_code", "status", "sponsor_count", "created_at")
    list_filter = ("status",)
    search_fields = ("deliverer__username", "referral_code")
    inlines = (SponsorInline,)
    readonly_fields = ("referral_code", "created_at", "updated_at")
