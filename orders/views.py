"""Commandes : validation du panier, suivi, espaces vendeur et livreur."""

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cart.models import Cart
from notifications.models import Notification
from notifications.services import notifier
from payments.models import Transaction
from payments.services import (
    confirm_transaction,
    demander_remboursement,
    get_wallet,
    start_transaction,
)
from payments.models import WalletEntry
from regions.utils import current_country

from . import services as order_services
from .models import Order, OrderEvent, OrderItem, OrderMessage, SellerConfirmation


@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    if cart.total_items == 0:
        messages.warning(request, "Votre panier est vide.")
        return redirect("cart")

    issues = cart.has_stock_issue()
    if issues:
        messages.error(
            request,
            "Certains articles ne sont plus disponibles en quantité suffisante. "
            "Ajustez votre panier avant de continuer.",
        )
        return redirect("cart")

    profile = request.user.profile

    if request.method == "POST":
        fulfilment = request.POST.get("fulfilment", Order.Fulfilment.DELIVERY)
        data = {
            "shipping_name": request.POST.get("shipping_name", "").strip(),
            "shipping_phone": request.POST.get("shipping_phone", "").strip(),
            "shipping_address": request.POST.get("shipping_address", "").strip(),
            "shipping_quartier": request.POST.get("shipping_quartier", "").strip(),
            "shipping_city": request.POST.get("shipping_city", "").strip() or "Ouagadougou",
        }
        data.pop("shipping_country", None)
        required = ["shipping_name", "shipping_phone"]
        if fulfilment == Order.Fulfilment.DELIVERY:
            required += ["shipping_address", "shipping_quartier"]

        if any(not data[f] for f in required):
            messages.error(request, "Merci de remplir tous les champs obligatoires.")
            return render(
                request,
                "orders/checkout.html",
                    {
                    "cart": cart, "profile": profile, "form": data, "fulfilment": fulfilment,
                    "avoir": get_wallet(request.user).available,
                    "delai_confirmation": settings.EAZYMARKET["ORDER_CONFIRMATION_HOURS"],
                },
            )

        with transaction.atomic():
            country = request.user.profile.country or current_country(request)
            order = Order.objects.create(
                user=request.user,
                country=country,
                shipping_country=country.name if country else "Burkina Faso",
                fulfilment=fulfilment,
                delivery_fee=cart.delivery_fee(fulfilment, data["shipping_city"]),
                delivery_notes=request.POST.get("delivery_notes", "").strip(),
                **data,
            )

            for item in cart.items_list:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                    seller=item.product.seller,
                    commission=item.commission,
                )

            order.recompute_totals()
            OrderEvent.objects.create(order=order, status=order.status, note="Commande créée")
            cart.items.all().delete()

            # L'avoir du client (remboursements précédents) règle la commande
            # en premier — c'est ce qui le fait revenir après une annulation.
            avoir = get_wallet(request.user).available
            credit = Decimal("0")
            if request.POST.get("utiliser_avoir") and avoir > 0:
                credit = min(avoir, order.total)
                order.credit_applied = credit
                order.save(update_fields=["credit_applied"])
                WalletEntry.objects.create(
                    wallet=get_wallet(request.user),
                    kind=WalletEntry.Kind.ADJUSTMENT,
                    amount=-credit,
                    label=f"Avoir utilisé sur la commande {order.order_number}",
                    is_released=True,
                    order=order,
                )

            reste = order.total - credit
            tx = start_transaction(
                user=request.user,
                purpose=Transaction.Purpose.ORDER,
                amount=reste,
                obj=order,
                payer_number=data["shipping_phone"],
                channel=Transaction.Channel.CREDIT if reste <= 0 else "",
            )

        if reste <= 0:
            confirm_transaction(tx)
            messages.success(
                request,
                f"Commande {order.order_number} réglée avec votre avoir. "
                "Le vendeur doit maintenant confirmer.",
            )
            return redirect("order_detail", order_id=order.id)

        messages.success(request, f"Commande {order.order_number} enregistrée. Dernière étape : le paiement.")
        return redirect("payment_pay", reference=tx.reference)

    initial = {
        "shipping_name": request.user.get_full_name() or request.user.username,
        "shipping_phone": profile.phone,
        "shipping_address": profile.address,
        "shipping_quartier": profile.quartier,
        "shipping_city": profile.city or "Ouagadougou",
    }
    return render(
        request,
        "orders/checkout.html",
        {
            "cart": cart,
            "profile": profile,
            "form": initial,
            "fulfilment": Order.Fulfilment.DELIVERY,
            "avoir": get_wallet(request.user).available,
            "delai_confirmation": settings.EAZYMARKET["ORDER_CONFIRMATION_HOURS"],
        },
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "events"), id=order_id, user=request.user
    )
    pending_tx = order.user.transactions.filter(
        object_type="order", object_id=order.id,
        status__in=[Transaction.Status.PENDING, Transaction.Status.AWAITING_REVIEW],
    ).first()
    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "pending_tx": pending_tx,
            "confirmations": order.confirmations.select_related("seller__profile"),
            "avoir": get_wallet(request.user).available,
            "remboursement_en_cours": request.user.wallet.payouts.filter(
                kind="refund", status__in=["requested", "processing"]
            ).first() if hasattr(request.user, "wallet") else None,
            "canaux": Transaction.Channel.choices,
            "refund_min": settings.EAZYMARKET["REFUND_MIN"],
            "jours_litige": settings.EAZYMARKET["DISPUTE_WINDOW_DAYS"],
            "thread": order.messages.select_related("sender"),
            "delai_confirmation": settings.EAZYMARKET["ORDER_CONFIRMATION_HOURS"],
        },
    )


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "orders/my_orders.html", {"orders": orders})


@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if not order.can_be_cancelled:
        messages.error(request, "Cette commande ne peut plus être annulée.")
    else:
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        OrderEvent.objects.create(
            order=order, status=order.status, note="Annulée par le client", by=request.user
        )
        messages.info(request, "Commande annulée.")
    return redirect("order_detail", order_id=order.id)


# ---------------------------------------------------------------------
# Vendeur
# ---------------------------------------------------------------------
@login_required
def seller_orders(request):
    if not request.user.profile.can_sell:
        return redirect("become_seller")

    items = (
        OrderItem.objects.filter(seller=request.user)
        .select_related("order", "order__user", "product")
        .order_by("-order__created_at")
    )
    grouped = {}
    for item in items:
        grouped.setdefault(item.order_id, {"order": item.order, "items": [], "total": Decimal("0")})
        grouped[item.order_id]["items"].append(item)
        grouped[item.order_id]["total"] += item.seller_amount

    a_confirmer = (
        SellerConfirmation.objects.filter(
            seller=request.user, status=SellerConfirmation.Status.PENDING
        )
        .select_related("order")
        .prefetch_related("order__items")
        .order_by("deadline")
    )

    return render(
        request,
        "orders/seller_orders.html",
        {
            "orders": list(grouped.values()),
            "a_confirmer": a_confirmer,
            "profile": request.user.profile,
            "JOURS_LITIGE": settings.EAZYMARKET["DISPUTE_WINDOW_DAYS"],
        },
    )


@login_required
@require_POST
def respond_confirmation(request, confirmation_id):
    """Le vendeur dit s'il a les articles de cette commande."""
    confirmation = get_object_or_404(
        SellerConfirmation, id=confirmation_id, seller=request.user
    )

    if not confirmation.is_pending:
        messages.info(request, "Vous avez déjà répondu à cette commande.")
        return redirect("seller_orders")

    accepte = request.POST.get("reponse") == "oui"
    note = request.POST.get("note", "").strip()

    order_services.repondre_confirmation(confirmation, accepte=accepte, note=note)

    if accepte:
        messages.success(
            request,
            f"Commande {confirmation.order.order_number} confirmée. "
            "Préparez-la, le livreur va être prévenu.",
        )
    else:
        messages.warning(
            request,
            f"Commande {confirmation.order.order_number} annulée et le client remboursé. "
            "Pensez à mettre votre stock à jour pour éviter que cela se reproduise.",
        )
    return redirect("seller_orders")


@login_required
@require_POST
def post_order_message(request, order_id):
    """Discussion client / vendeur sur une commande, sans échange de numéros."""
    order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id)

    est_client = order.user_id == request.user.id
    est_vendeur = order.items.filter(seller=request.user).exists()
    if not (est_client or est_vendeur or request.user.is_staff):
        messages.error(request, "Accès refusé.")
        return redirect("home")

    corps = request.POST.get("body", "").strip()
    if corps:
        OrderMessage.objects.create(
            order=order, sender=request.user, body=corps,
            attachment=request.FILES.get("attachment"),
        )
        if est_client:
            destinataires = [i.seller for i in order.items.all() if i.seller_id]
        else:
            destinataires = [order.user]
        for destinataire in set(destinataires):
            notifier(
                destinataire,
                f"Message — commande {order.order_number}",
                corps[:120],
                lien=f"/commandes/{order.id}/",
            )
        messages.success(request, "Message envoyé.")

    if est_client:
        return redirect("order_detail", order_id=order.id)
    return redirect("seller_orders")


# ---------------------------------------------------------------------
# Livreur
# ---------------------------------------------------------------------
@login_required
def delivery_orders(request):
    if not request.user.profile.can_deliver:
        return redirect("become_delivery")
    orders = Order.objects.filter(delivery_driver=request.user)
    return render(request, "orders/delivery_orders.html", {"orders": orders})


@login_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    profile_obj = request.user.profile
    role = profile_obj.user_type

    allowed = False
    if request.user.is_staff:
        allowed = True
    elif profile_obj.can_sell and OrderItem.objects.filter(order=order, seller=request.user).exists():
        allowed = True
    elif profile_obj.can_deliver and order.delivery_driver == request.user:
        allowed = True

    if not allowed:
        messages.error(request, "Vous ne pouvez pas modifier cette commande.")
        return redirect("home")

    new_status = request.POST.get("status")
    if new_status not in dict(Order.Status.choices):
        messages.error(request, "Statut inconnu.")
        return redirect("order_detail", order_id=order.id)

    if new_status == Order.Status.DELIVERED:
        # Passe par le service : c'est lui qui démarre le compte à rebours du
        # paiement vendeur et prévient le client qu'il peut contester.
        order_services.marquer_livree(order, par=request.user)
        if role == "delivery":
            profile_obj.total_deliveries += 1
            profile_obj.save(update_fields=["total_deliveries"])
    else:
        order.status = new_status
        order.save()

    OrderEvent.objects.create(
        order=order, status=new_status, note=request.POST.get("note", ""), by=request.user
    )
    notifier(
        order.user,
        f"Commande {order.order_number}",
        f"Statut mis à jour : {order.get_status_display()}",
        lien=f"/commandes/{order.id}/",
        # Prête ou en route : le client doit être joignable tout de suite.
        urgent=new_status in (Order.Status.READY, Order.Status.SHIPPED),
    )
    messages.success(request, f"Statut mis à jour : {order.get_status_display()}")
    return redirect(request.META.get("HTTP_REFERER", "home"))


@login_required
@require_POST
def signaler_non_recu(request, order_id):
    """Le client déclare ne pas avoir reçu sa commande."""
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if not order.delivered_at:
        messages.info(request, "Cette commande n'est pas encore marquée comme livrée.")
        return redirect("order_detail", order_id=order.id)
    if not order.fenetre_contestation_ouverte:
        messages.error(
            request,
            "Le délai de signalement est passé. Écrivez-nous sur WhatsApp, "
            "on regardera votre dossier.",
        )
        return redirect("order_detail", order_id=order.id)

    order_services.signaler_non_recu(
        order, note=request.POST.get("note", "").strip(), par=request.user
    )
    messages.warning(
        request,
        "Signalement enregistré. Le paiement du vendeur est suspendu et nous "
        "vous recontactons. Expliquez la situation dans la messagerie de la commande.",
    )
    return redirect("order_detail", order_id=order.id)


@login_required
@require_POST
def demander_mon_remboursement(request, order_id):
    """Le client veut son avoir en argent réel, sur son mobile money."""
    order = get_object_or_404(Order, id=order_id, user=request.user)

    payout, message = demander_remboursement(
        request.user,
        montant=request.POST.get("montant") or None,
        numero=request.POST.get("numero", "").strip(),
        canal=request.POST.get("canal", "").strip(),
        order=order,
    )
    if payout:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("order_detail", order_id=order.id)


@login_required
@require_POST
def confirmer_reception(request, order_id):
    """Le client déclare avoir reçu sa commande.

    C'est le signal le plus fiable qui soit : personne n'a intérêt à dire
    qu'il a reçu s'il n'a rien reçu. On déclenche donc la livraison, et on
    n'ouvre pas de fenêtre de contestation — il n'y a rien à contester.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.delivered_at:
        messages.info(request, "Cette commande est déjà marquée comme reçue.")
        return redirect("order_detail", order_id=order.id)
    if not order.is_paid:
        messages.error(request, "Cette commande n'est pas encore payée.")
        return redirect("order_detail", order_id=order.id)

    order.reception_confirmee = True
    order.save(update_fields=["reception_confirmee", "updated_at"])
    order_services.marquer_livree(order, par=request.user)

    messages.success(
        request,
        "Merci ! Le vendeur va être payé. Si quelque chose ne va pas avec "
        "l'article, écrivez-nous depuis la messagerie de la commande.",
    )
    return redirect("order_detail", order_id=order.id)
