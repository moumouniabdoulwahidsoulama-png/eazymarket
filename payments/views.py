"""Vues des paiements, du portefeuille et du back-office financier."""

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from regions.utils import current_country

from .models import Payout, Transaction, WalletEntry
from .providers import get_provider
from .services import confirm_transaction, get_wallet, reject_transaction, request_payout

logger = logging.getLogger("payments")


def _redirect_after(tx):
    if tx.purpose == Transaction.Purpose.ORDER and tx.object_id:
        return redirect("order_detail", order_id=tx.object_id)
    if tx.purpose == Transaction.Purpose.SUBSCRIPTION:
        return redirect("artisan_dashboard")
    return redirect("home")


# ---------------------------------------------------------------------
# Parcours de paiement
# ---------------------------------------------------------------------
@login_required
def pay(request, reference):
    """Page de paiement : choix du canal puis lancement."""
    tx = get_object_or_404(Transaction, reference=reference, user=request.user)

    if tx.status == Transaction.Status.SUCCESS:
        messages.info(request, "Ce paiement a déjà été confirmé.")
        return _redirect_after(tx)

    provider = get_provider()
    country = current_country(request)
    channels = (
        provider.available_channels(country)
        if callable(getattr(provider, "available_channels", None))
        else provider.channels
    )

    if request.method == "POST":
        channel = request.POST.get("channel") or (channels[0] if channels else "orange_money")
        if channel not in list(channels) + ["cash"]:
            messages.error(request, "Moyen de paiement indisponible.")
            return redirect("payment_pay", reference=reference)

        tx.channel = channel
        tx.payer_number = request.POST.get("payer_number", "").strip()
        tx.save(update_fields=["channel", "payer_number"])

        result = provider.initiate(tx, request=request, country=country)
        if not result.ok:
            messages.error(request, result.message)
            return redirect("payment_pay", reference=reference)
        if result.mode == "redirect" and result.redirect_url:
            return redirect(result.redirect_url)
        return redirect("payment_declare", reference=reference)

    return render(
        request,
        "payments/pay.html",
        {"tx": tx, "provider": provider, "channels": channels, "country": country},
    )


@login_required
def declare(request, reference):
    """Mode manuel : l'acheteur déclare l'identifiant de sa transaction."""
    tx = get_object_or_404(Transaction, reference=reference, user=request.user)
    provider = get_provider()
    accounts = (
        provider.accounts_for(tx.channel or "", tx.amount, current_country(request))
        if hasattr(provider, "accounts_for")
        else []
    )

    if tx.status == Transaction.Status.SUCCESS:
        return _redirect_after(tx)

    if request.method == "POST":
        operator_id = request.POST.get("operator_id", "").strip()
        payer_number = request.POST.get("payer_number", "").strip()

        if len(operator_id) < 4:
            messages.error(request, "Saisissez l'identifiant de transaction reçu par SMS.")
            return redirect("payment_declare", reference=reference)

        tx.provider_reference = operator_id
        tx.payer_number = payer_number or tx.payer_number
        tx.status = Transaction.Status.AWAITING_REVIEW
        if "proof" in request.FILES:
            tx.proof = request.FILES["proof"]
        tx.save()

        # Sans cette alerte, un paiement déclaré attendait que quelqu'un
        # pense à ouvrir le back-office. Le client, lui, avait déjà payé.
        from notifications.services import alerter_les_admins

        montant = f"{tx.amount:,.0f}".replace(",", " ")
        alerter_les_admins(
            f"Paiement à valider — {montant} FCFA",
            f"{request.user.username} déclare avoir payé {montant} FCFA "
            f"({tx.get_purpose_display()}) depuis le "
            f"{tx.payer_number or 'numéro non précisé'}. "
            f"Référence opérateur : {operator_id}. "
            "Vérifiez le versement sur votre compte marchand, puis validez.",
            lien="/paiement/admin/transactions/",
            sms_texte=(f"EazyMarket : paiement de {montant} FCFA a valider "
                       f"(ref {operator_id}). Le client attend."),
        )

        messages.success(
            request,
            "Paiement déclaré. Nous vérifions et confirmons sous quelques minutes "
            "— vous recevrez une notification.",
        )
        return _redirect_after(tx)

    return render(request, "payments/declare.html", {"tx": tx, "accounts": accounts})


@login_required
def payment_return(request, reference):
    """Retour depuis la page de l'opérateur : on re-vérifie côté serveur."""
    tx = get_object_or_404(Transaction, reference=reference, user=request.user)
    provider = get_provider()

    if tx.status != Transaction.Status.SUCCESS and provider.verify(tx):
        confirm_transaction(tx)
        messages.success(request, "Paiement confirmé. Merci !")
    elif tx.status != Transaction.Status.SUCCESS:
        messages.warning(
            request,
            "Le paiement n'est pas encore confirmé. Si vous avez été débité, "
            "la confirmation arrive dans quelques instants.",
        )
    return _redirect_after(tx)


@login_required
def status(request, reference):
    tx = get_object_or_404(Transaction, reference=reference, user=request.user)
    return JsonResponse({"status": tx.status, "label": tx.get_status_display()})


@csrf_exempt
@require_POST
def webhook(request):
    """Notification serveur-à-serveur de l'agrégateur."""
    provider = get_provider()
    tx, ok = provider.handle_webhook(request)
    if tx and ok:
        confirm_transaction(tx)
    return HttpResponse("OK")


# ---------------------------------------------------------------------
# Portefeuille du vendeur / artisan
# ---------------------------------------------------------------------
@login_required
def wallet_view(request):
    wallet = get_wallet(request.user)
    entries = wallet.entries.select_related("order")[:60]
    return render(
        request,
        "payments/wallet.html",
        {
            "wallet": wallet,
            "entries": entries,
            "payouts": wallet.payouts.all()[:10],
            "channels": Transaction.Channel.choices,
        },
    )


@login_required
@require_POST
def wallet_withdraw(request):
    amount = request.POST.get("amount") or None
    payout, message = request_payout(request.user, amount)
    if payout:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("wallet")


@login_required
@require_POST
def wallet_settings(request):
    wallet = get_wallet(request.user)
    wallet.payout_channel = request.POST.get("payout_channel", wallet.payout_channel)
    wallet.payout_number = request.POST.get("payout_number", "").strip()
    wallet.payout_name = request.POST.get("payout_name", "").strip()
    wallet.save()
    messages.success(request, "Coordonnées de retrait enregistrées.")
    return redirect("wallet")


# ---------------------------------------------------------------------
# Back-office
# ---------------------------------------------------------------------
@staff_member_required
def admin_transactions(request):
    qs = Transaction.objects.select_related("user")
    state = request.GET.get("etat", "awaiting_review")
    if state != "all":
        qs = qs.filter(status=state)
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(reference__icontains=query)
            | Q(provider_reference__icontains=query)
            | Q(payer_number__icontains=query)
            | Q(user__username__icontains=query)
        )
    return render(
        request,
        "payments/admin_transactions.html",
        {
            "transactions": qs[:200],
            "state": state,
            "query": query,
            "counts": {
                "awaiting_review": Transaction.objects.filter(status="awaiting_review").count(),
                "pending": Transaction.objects.filter(status="pending").count(),
            },
        },
    )


@staff_member_required
@require_POST
def admin_review(request, reference, action):
    tx = get_object_or_404(Transaction, reference=reference)
    if action == "valider":
        confirm_transaction(tx, by=request.user)
        _notify(tx.user, "Paiement confirmé", f"Votre paiement {tx.reference} a été confirmé.")
        messages.success(request, f"{tx.reference} confirmée.")
    elif action == "refuser":
        reject_transaction(tx, by=request.user, reason=request.POST.get("reason", ""))
        _notify(tx.user, "Paiement non confirmé", f"Le paiement {tx.reference} n'a pas pu être vérifié.")
        messages.warning(request, f"{tx.reference} refusée.")
    return redirect(request.META.get("HTTP_REFERER", "admin_transactions"))


@staff_member_required
def admin_payouts(request):
    payouts = Payout.objects.select_related("wallet__user")
    state = request.GET.get("etat", "requested")
    if state != "all":
        payouts = payouts.filter(status=state)
    return render(request, "payments/admin_payouts.html", {"payouts": payouts[:200], "state": state})


@staff_member_required
@require_POST
def admin_payout_paid(request, reference):
    payout = get_object_or_404(Payout, reference=reference)
    payout.provider_reference = request.POST.get("provider_reference", "")
    payout.mark_paid(by=request.user)
    _notify(
        payout.wallet.user,
        "Retrait versé",
        f"Votre retrait de {payout.amount:,.0f} FCFA a été envoyé sur {payout.number}.".replace(",", " "),
        urgent=True,
    )
    messages.success(request, f"Retrait {payout.reference} marqué comme versé.")
    return redirect("admin_payouts")


def _notify(user, title, message, link="", urgent=False):
    """Notification interne, doublée d'un SMS quand c'est important."""
    try:
        from notifications.services import notifier

        notifier(user, title, message, lien=link, urgent=urgent)
    except Exception:  # noqa: BLE001
        logger.exception("Notification non envoyée")
