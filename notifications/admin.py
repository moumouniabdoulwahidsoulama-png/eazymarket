from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_urgent", "sms_status", "is_read", "created_at")
    list_filter = ("is_urgent", "sms_status", "is_read")
    search_fields = ("user__username", "title", "message")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
