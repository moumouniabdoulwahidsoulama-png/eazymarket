from django.contrib import admin

from .models import Order, OrderEvent, OrderItem, OrderMessage, SellerConfirmation


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "product_price", "quantity", "subtotal", "commission")


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ("created_at",)


class SellerConfirmationInline(admin.TabularInline):
    model = SellerConfirmation
    extra = 0
    readonly_fields = ("seller", "amount", "commission", "deadline", "responded_at")


@admin.register(SellerConfirmation)
class SellerConfirmationAdmin(admin.ModelAdmin):
    list_display = ("order", "seller", "amount", "status", "deadline", "responded_at")
    list_filter = ("status",)
    search_fields = ("order__order_number", "seller__username")
    date_hierarchy = "deadline"


admin.site.register(OrderMessage)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "total", "status", "is_paid", "created_at")
    list_filter = ("status", "is_paid", "fulfilment")
    list_select_related = ("user",)
    search_fields = ("order_number", "user__username", "shipping_phone")
    inlines = (OrderItemInline, SellerConfirmationInline, OrderEventInline)
    date_hierarchy = "created_at"
    readonly_fields = ("order_number", "subtotal", "commission_total", "total")
