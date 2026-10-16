from django.contrib import admin, messages

from .models import Payout, Transaction, Wallet, WalletEntry
from .services import confirm_transaction, reject_transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "purpose", "amount", "channel", "status", "created_at")
    list_filter = ("status", "purpose", "channel", "provider")
    search_fields = ("reference", "provider_reference", "payer_number", "user__username")
    readonly_fields = ("reference", "created_at", "updated_at", "raw_response")
    actions = ("action_confirm", "action_reject")
    date_hierarchy = "created_at"

    @admin.action(description="Confirmer les paiements sélectionnés")
    def action_confirm(self, request, queryset):
        done = 0
        for tx in queryset:
            confirm_transaction(tx, by=request.user)
            done += 1
        self.message_user(request, f"{done} transaction(s) confirmée(s).", messages.SUCCESS)

    @admin.action(description="Refuser les paiements sélectionnés")
    def action_reject(self, request, queryset):
        for tx in queryset:
            reject_transaction(tx, by=request.user, reason="Refusé depuis l'admin")
        self.message_user(request, "Transactions refusées.", messages.WARNING)


class WalletEntryInline(admin.TabularInline):
    model = WalletEntry
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "payout_channel", "payout_number", "available", "locked", "pending")
    search_fields = ("user__username", "payout_number")
    inlines = (WalletEntryInline,)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("reference", "nature", "wallet", "amount", "channel", "number",
                    "status", "created_at")
    list_filter = ("kind", "status", "channel")
    search_fields = ("reference", "number", "wallet__user__username")
    actions = ("action_paid",)

    @admin.display(description="Nature", ordering="kind")
    def nature(self, obj):
        # Un remboursement client et un retrait vendeur se paient pareil, mais
        # il faut voir d'un coup d'œil à qui on envoie de l'argent et pourquoi.
        return "⟲ Remboursement client" if obj.kind == obj.Kind.REFUND else "↑ Retrait vendeur"

    @admin.action(description="Marquer comme versé")
    def action_paid(self, request, queryset):
        for payout in queryset:
            payout.mark_paid(by=request.user)
        self.message_user(request, "Retraits marqués comme versés.", messages.SUCCESS)
