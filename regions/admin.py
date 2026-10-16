from django.contrib import admin

from .models import City, Country, PaymentAccount


class CityInline(admin.TabularInline):
    model = City
    extra = 1


class PaymentAccountInline(admin.TabularInline):
    model = PaymentAccount
    extra = 1


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "currency_symbol", "main_city", "is_active", "is_default", "order")
    list_editable = ("is_active", "order")
    search_fields = ("name", "code")
    inlines = (CityInline, PaymentAccountInline)
    fieldsets = (
        ("Identité", {"fields": ("name", "code", "slug", "flag", "dial_code", "main_city")}),
        ("Monnaie", {"fields": ("currency_code", "currency_symbol")}),
        ("Assistance", {"fields": ("support_phone", "support_whatsapp")}),
        ("Ouverture", {"fields": ("is_active", "is_default", "order")}),
        ("Tarifs locaux (0 = valeur par défaut du .env)", {
            "fields": ("shop_pack_price", "artisan_sub_price", "contact_unlock_price",
                       "delivery_fee_city", "delivery_fee_out", "free_delivery_from", "payout_min"),
        }),
    )


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "is_main", "delivery_fee", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("name",)


@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ("country", "channel", "number", "holder", "ussd_template", "is_active")
    list_filter = ("country", "channel", "is_active")
    search_fields = ("number", "holder")
