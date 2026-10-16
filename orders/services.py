"""
Cycle de vie d'une commande après paiement.

Le principe : **l'argent du client reste chez la plateforme** tant que le
vendeur n'a pas confirmé qu'il a l'article. C'est ce qui permet de promettre
un remboursement automatique, et donc de convaincre quelqu'un de payer en
ligne un commerçant qu'il ne connaît pas.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from notifications.services import alerter_les_admins, notifier
from payments.models import Wallet, WalletEntry
from payments.services import get_wallet

from .models import Order, OrderEvent, SellerConfirmation

logger = logging.getLogger("orders")


def _fmt(montant):
    return f"{int(montant):,}".replace(",", " ")


# ---------------------------------------------------------------------
# Ouverture du délai de confirmation
# ---------------------------------------------------------------------
@db_transaction.atomic
def ouvrir_les_confirmations(order):
    """Après paiement : réserve le stock et demande leur accord aux vendeurs."""
    heures = settings.EAZYMARKET["ORDER_CONFIRMATION_HOURS"]
    limite = timezone.now() + timedelta(hours=heures)

    parts = {}
    for item in order.items.select_related("product", "seller"):
        # Réservation du stock : deux clients ne peuvent pas acheter le dernier
        produit = item.product
        if produit and not produit.made_to_order:
            produit.stock = max(0, produit.stock - item.quantity)
            if produit.stock == 0:
                produit.is_available = False
            produit.save(update_fields=["stock", "is_available"])

        if item.seller_id:
            part = parts.setdefault(item.seller_id, {"montant": Decimal("0"),
                                                     "commission": Decimal("0"),
                                                     "vendeur": item.seller})
            part["montant"] += item.subtotal
            part["commission"] += item.commission

    for seller_id, part in parts.items():
        SellerConfirmation.objects.get_or_create(
            order=order, seller_id=seller_id,
            defaults={"amount": part["montant"], "commission": part["commission"],
                      "deadline": limite},
        )

    order.status = Order.Status.AWAITING
    order.confirmation_deadline = limite
    order.save(update_fields=["status", "confirmation_deadline", "updated_at"])
    OrderEvent.objects.create(
        order=order, status=order.status,
        note=f"Paiement reçu — confirmation des vendeurs sous {heures} h",
    )

    for part in parts.values():
        vendeur = part["vendeur"]
        notifier(
            vendeur,
            f"Nouvelle commande {order.order_number}",
            f"{_fmt(part['montant'])} FCFA. Confirmez sous {heures} h que vous avez "
            "les articles, sinon la commande est annulée.",
            lien=f"/commandes/vendeur/",
            urgent=True,
            sms_texte=(
                f"EazyMarket : nouvelle commande {order.order_number} de "
                f"{_fmt(part['montant'])} FCFA. Confirmez sous {heures}h."
            ),
        )

    notifier(
        order.user,
        f"Paiement reçu — commande {order.order_number}",
        f"Votre argent est conservé par {settings.EAZYMARKET['SITE_NAME']} le temps que "
        f"le vendeur confirme. Sans réponse sous {heures} h, vous êtes remboursé.",
        lien=f"/commandes/{order.id}/",
    )
    return order


# ---------------------------------------------------------------------
# Réponse d'un vendeur
# ---------------------------------------------------------------------
@db_transaction.atomic
def repondre_confirmation(confirmation, accepte, note="", auto=False):
    """Le vendeur dit s'il a les articles. Idempotent."""
    if not confirmation.is_pending:
        return confirmation

    order = confirmation.order
    profil = confirmation.seller.profile
    maintenant = timezone.now()

    if accepte:
        confirmation.status = SellerConfirmation.Status.ACCEPTED
        confirmation.responded_at = maintenant
        confirmation.note = note[:250]
        confirmation.save(update_fields=["status", "responded_at", "note"])

        # Le vendeur est crédité, mais SANS échéance de libération.
        #
        # Le compte à rebours ne démarre qu'à la livraison : confirmer ne suffit
        # pas à être payé, il faut que le client ait reçu. Sans cela, un vendeur
        # pourrait confirmer, ne rien livrer, et encaisser trois jours plus tard.
        for item in confirmation.items.select_related("product"):
            WalletEntry.objects.create(
                wallet=get_wallet(confirmation.seller),
                kind=WalletEntry.Kind.SALE,
                amount=item.seller_amount,
                label=f"Vente {item.quantity}× {item.product_name} (cmd {order.order_number})",
                is_released=False,
                release_at=None,
                order=order,
            )
            if item.product:
                item.product.sold_count = (item.product.sold_count or 0) + item.quantity
                item.product.save(update_fields=["sold_count"])

        minutes = int((maintenant - order.paid_at).total_seconds() // 60) if order.paid_at else 0
        profil.orders_confirmed += 1
        profil.confirmation_minutes_total += max(0, minutes)
        profil.save(update_fields=["orders_confirmed", "confirmation_minutes_total"])

        notifier(
            order.user,
            f"Commande {order.order_number} confirmée",
            f"{profil.display_name} a confirmé votre commande. Préparation en cours.",
            lien=f"/commandes/{order.id}/",
        )
    else:
        confirmation.status = (
            SellerConfirmation.Status.EXPIRED if auto else SellerConfirmation.Status.REFUSED
        )
        confirmation.responded_at = maintenant
        confirmation.note = note[:250]
        confirmation.save(update_fields=["status", "responded_at", "note"])

        _rendre_le_stock(confirmation)
        _rembourser(order, confirmation.amount,
                    motif="sans réponse du vendeur" if auto else "article indisponible")

        profil.orders_cancelled += 1
        profil.save(update_fields=["orders_cancelled"])
        _appliquer_les_sanctions(profil)

        notifier(
            order.user,
            f"Une partie de la commande {order.order_number} est annulée",
            f"{profil.display_name} ne peut pas fournir ses articles. "
            f"{_fmt(confirmation.amount)} FCFA sont sur votre compte, utilisables "
            "tout de suite. Vous pouvez aussi demander à les recevoir sur votre "
            "mobile money.",
            lien=f"/commandes/{order.id}/",
            urgent=True,
            sms_texte=(
                f"EazyMarket : {_fmt(confirmation.amount)} FCFA vous ont ete rendus "
                f"(commande {order.order_number}, article indisponible). Gardez-les "
                "en avoir ou demandez le virement dans l'application."
            ),
        )

    _recalculer_le_statut(order)
    return confirmation


def _rendre_le_stock(confirmation):
    for item in confirmation.items.select_related("product"):
        produit = item.product
        if produit and not produit.made_to_order:
            produit.stock += item.quantity
            produit.is_available = True
            produit.save(update_fields=["stock", "is_available"])


def _rembourser(order, montant, motif=""):
    """Recrédite le client sous forme d'avoir, immédiatement utilisable."""
    if montant <= 0:
        return
    WalletEntry.objects.create(
        wallet=get_wallet(order.user),
        kind=WalletEntry.Kind.REFUND,
        amount=montant,
        label=f"Remboursement commande {order.order_number} ({motif})".strip(),
        is_released=True,
        order=order,
    )
    order.refunded_amount = (order.refunded_amount or 0) + montant
    order.save(update_fields=["refunded_amount", "updated_at"])
    # Pas de notification ici : cette fonction sert aussi à rembourser les
    # frais de livraison d'une commande déjà annulée. C'est l'appelant qui
    # prévient le client, une seule fois, avec le bon message.


def _appliquer_les_sanctions(profil):
    """Trop d'annulations : la boutique est suspendue automatiquement."""
    seuil = settings.EAZYMARKET["SELLER_MAX_CANCELLATIONS"]
    if profil.orders_cancelled >= seuil and not profil.is_store_suspended:
        profil.is_store_suspended = True
        profil.suspended_reason = (
            f"{profil.orders_cancelled} commandes annulées faute de stock. "
            "Mettez votre stock à jour puis contactez-nous pour rouvrir."
        )
        profil.save(update_fields=["is_store_suspended", "suspended_reason"])
        notifier(
            profil.user,
            "Votre boutique est suspendue",
            profil.suspended_reason,
            lien="/compte/vendeur/",
            urgent=True,
            sms_texte="EazyMarket : votre boutique est suspendue (trop d'annulations). Contactez-nous.",
        )
        logger.warning("Boutique suspendue : %s", profil.user)


def _recalculer_le_statut(order):
    """Fait avancer la commande quand tous les vendeurs ont répondu."""
    confirmations = list(order.confirmations.all())
    if not confirmations or any(c.is_pending for c in confirmations):
        return

    acceptees = [c for c in confirmations
                 if c.status == SellerConfirmation.Status.ACCEPTED]

    if acceptees:
        order.status = Order.Status.PREPARING
        order.confirmed_at = timezone.now()
        note = "Confirmée par le vendeur"
        if len(acceptees) < len(confirmations):
            note = "Confirmée en partie — le reste a été remboursé"
    else:
        order.status = Order.Status.CANCELLED
        order.cancel_reason = (
            Order.CancelReason.NO_ANSWER
            if all(c.status == SellerConfirmation.Status.EXPIRED for c in confirmations)
            else Order.CancelReason.NO_STOCK
        )
        note = "Annulée — aucun vendeur n'a pu fournir"
        # Les frais de livraison n'ont plus lieu d'être
        if order.delivery_fee:
            _rembourser(order, order.delivery_fee, motif="frais de livraison")

    order.save(update_fields=["status", "confirmed_at", "cancel_reason", "updated_at"])
    OrderEvent.objects.create(order=order, status=order.status, note=note)


# ---------------------------------------------------------------------
# Tâche automatique
# ---------------------------------------------------------------------
def traiter_les_commandes_expirees():
    """Annule les parts de commande non confirmées dans le délai."""
    expirees = SellerConfirmation.objects.filter(
        status=SellerConfirmation.Status.PENDING, deadline__lte=timezone.now()
    ).select_related("order", "seller__profile")

    total = 0
    for confirmation in expirees:
        repondre_confirmation(confirmation, accepte=False, auto=True,
                              note="Aucune réponse dans le délai")
        total += 1
    if total:
        logger.info("%s confirmation(s) expirée(s) traitée(s)", total)
    return total


# ---------------------------------------------------------------------
# Livraison : c'est elle qui déclenche le paiement du vendeur
# ---------------------------------------------------------------------
def marquer_livree(order, par=None):
    """La commande est arrivée : le compte à rebours du vendeur démarre.

    Tant que personne n'a marqué la livraison, l'argent du vendeur reste
    bloqué sans échéance. C'est ici, et seulement ici, qu'on pose la date
    de libération.
    """
    maintenant = timezone.now()
    if not order.delivered_at:
        order.delivered_at = maintenant
    order.status = Order.Status.DELIVERED
    order.save(update_fields=["delivered_at", "status", "updated_at"])

    delai = settings.EAZYMARKET["PAYOUT_DELAY_DAYS"]
    jours_litige = settings.EAZYMARKET["DISPUTE_WINDOW_DAYS"]
    echeance = maintenant + timedelta(days=delai)

    lignes = WalletEntry.objects.filter(
        order=order, kind=WalletEntry.Kind.SALE, is_released=False, release_at__isnull=True
    )
    nombre = lignes.update(release_at=echeance)

    # Le livreur touche la totalité des frais de livraison, crédités à la
    # remise comme la part du vendeur. Sans ça, il livrerait gratuitement.
    if order.delivery_driver_id and order.delivery_fee and order.fulfilment == Order.Fulfilment.DELIVERY:
        deja = WalletEntry.objects.filter(
            order=order, kind=WalletEntry.Kind.DELIVERY
        ).exists()
        if not deja:
            WalletEntry.objects.create(
                wallet=get_wallet(order.delivery_driver),
                kind=WalletEntry.Kind.DELIVERY,
                amount=order.delivery_fee,
                label=f"Livraison commande {order.order_number}",
                is_released=False,
                release_at=echeance,
                order=order,
            )
            notifier(
                order.delivery_driver,
                f"Course {order.order_number} payée",
                f"{_fmt(order.delivery_fee)} FCFA pour cette livraison seront "
                f"disponibles sur votre solde dans {delai} jours.",
                lien="/compte/livreur/",
            )

    OrderEvent.objects.create(
        order=order, status=Order.Status.DELIVERED,
        note="Livraison enregistrée", by=par,
    )

    notifier(
        order.user,
        f"Commande {order.order_number} livrée",
        f"Si vous n'avez rien reçu, signalez-le sous {jours_litige} jours : "
        "l'argent du vendeur est bloqué jusque-là.",
        lien=f"/commandes/{order.id}/",
        urgent=True,
        sms_texte=(
            f"EazyMarket : commande {order.order_number} marquee livree. "
            f"Rien recu ? Signalez-le sous {jours_litige} jours dans l'application."
        ),
    )
    logger.info("Commande %s livrée — %s ligne(s) programmée(s)", order.order_number, nombre)
    return nombre


def signaler_non_recu(order, note="", par=None):
    """Le client dit qu'il n'a rien reçu : on regèle l'argent du vendeur.

    On ne rembourse pas automatiquement — c'est la parole de l'un contre
    celle de l'autre, et un remboursement automatique serait une porte
    ouverte aux abus. On bloque, et un humain tranche.
    """
    if order.non_recu_signale:
        return 0

    order.non_recu_signale = True
    order.non_recu_note = note[:250]
    order.non_recu_at = timezone.now()
    order.save(update_fields=["non_recu_signale", "non_recu_note", "non_recu_at", "updated_at"])

    # On remet les gains du vendeur hors d'atteinte, y compris ceux dont
    # l'échéance était proche.
    # On rebloque tout ce qui n'est pas encore libéré pour cette commande :
    # la part du vendeur ET les frais du livreur. Si le client n'a rien reçu,
    # la livraison elle-même est en cause.
    bloquees = WalletEntry.objects.filter(
        order=order,
        kind__in=[WalletEntry.Kind.SALE, WalletEntry.Kind.DELIVERY],
        is_released=False,
    ).update(release_at=None)

    OrderEvent.objects.create(
        order=order, status=order.status,
        note=f"Le client signale n'avoir rien reçu. {note}".strip(), by=par,
    )

    for vendeur in {i.seller for i in order.items.all() if i.seller_id}:
        notifier(
            vendeur,
            f"Litige sur la commande {order.order_number}",
            "Le client déclare ne pas avoir reçu sa commande. Votre paiement "
            "est suspendu le temps qu'on vérifie. Répondez dans la messagerie "
            "de la commande.",
            lien="/commandes/vendeur/",
            urgent=True,
        )

    alerter_les_admins(
        f"Litige à arbitrer — {order.order_number}",
        f"{order.user.username} déclare ne pas avoir reçu sa commande. "
        f"{bloquees} ligne(s) de paiement bloquée(s) chez le vendeur.",
        lien=f"/commandes/{order.id}/",
    )

    logger.warning("Non-réception signalée : %s", order.order_number)
    return bloquees


def commandes_sans_livraison():
    """Commandes confirmées depuis longtemps et jamais marquées livrées.

    Ce n'est pas forcément une fraude — souvent le vendeur oublie de cliquer.
    Mais l'argent du client est immobilisé, donc il faut que ça se voie.
    """
    jours = settings.EAZYMARKET["DELIVERY_ALERT_DAYS"]
    limite = timezone.now() - timedelta(days=jours)
    return (
        Order.objects.filter(
            is_paid=True,
            delivered_at__isnull=True,
            confirmations__status=SellerConfirmation.Status.ACCEPTED,
            confirmations__responded_at__lte=limite,
        )
        .exclude(status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])
        .distinct()
    )
