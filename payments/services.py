"""
Logique métier des paiements : c'est ici — et nulle part ailleurs —
qu'une commande devient « payée » et qu'un vendeur est crédité.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Payout, Transaction, Wallet, WalletEntry

logger = logging.getLogger("payments")


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def start_transaction(*, user, purpose, amount, channel="", obj=None, payer_number=""):
    """Crée une transaction en attente pour un objet métier."""
    tx = Transaction.objects.create(
        user=user,
        purpose=purpose,
        amount=Decimal(int(amount)),
        channel=channel,
        payer_number=payer_number,
        object_type=obj.__class__.__name__.lower() if obj is not None else "",
        object_id=getattr(obj, "pk", None),
    )
    return tx


@db_transaction.atomic
def confirm_transaction(tx, *, by=None):
    """Confirme une transaction et déclenche l'effet métier correspondant.

    Idempotent : appeler deux fois ne crédite pas deux fois.
    """
    if tx.status == Transaction.Status.SUCCESS:
        return tx

    tx.status = Transaction.Status.SUCCESS
    tx.confirmed_at = timezone.now()
    tx.reviewed_by = by
    tx.save(update_fields=["status", "confirmed_at", "reviewed_by", "updated_at"])

    if tx.purpose == Transaction.Purpose.ORDER:
        _settle_order(tx)
    elif tx.purpose == Transaction.Purpose.SUBSCRIPTION:
        _activate_subscription(tx)
    elif tx.purpose == Transaction.Purpose.SHOP_PACK:
        _add_shop_slots(tx)
    elif tx.purpose == Transaction.Purpose.VIDEO_PACK:
        _add_video_slots(tx)
    elif tx.purpose == Transaction.Purpose.CONTACT:
        _unlock_contact(tx)
    elif tx.purpose == Transaction.Purpose.BOOST:
        _activate_boost(tx)

    logger.info("Transaction confirmée %s (%s FCFA)", tx.reference, tx.amount)
    return tx


def reject_transaction(tx, *, by=None, reason=""):
    tx.status = Transaction.Status.FAILED
    tx.reviewed_by = by
    tx.notes = (tx.notes + "\n" + reason).strip()
    tx.save(update_fields=["status", "reviewed_by", "notes", "updated_at"])
    return tx


# ---------------------------------------------------------------------
# Effets métier
# ---------------------------------------------------------------------
def _settle_order(tx):
    """Paiement encaissé : on réserve le stock et on interroge les vendeurs.

    Le vendeur n'est PAS crédité ici — seulement quand il aura confirmé qu'il
    a bien l'article. C'est ce délai qui permet de rembourser le client
    automatiquement si le produit n'existe pas.
    """
    from orders.models import Order
    from orders.services import ouvrir_les_confirmations

    try:
        order = Order.objects.select_for_update().get(pk=tx.object_id)
    except Order.DoesNotExist:
        logger.error("Transaction %s : commande %s introuvable", tx.reference, tx.object_id)
        return

    if order.is_paid:
        return

    order.is_paid = True
    order.paid_at = timezone.now()
    order.payment_method = tx.get_channel_display() or tx.provider
    order.payment_reference = tx.reference
    order.save()

    ouvrir_les_confirmations(order)


def _activate_subscription(tx):
    """Active ou prolonge l'abonnement d'un artisan.

    La durée vient de ARTISAN_SUB_DAYS (90 jours par défaut), multipliée
    par le nombre de périodes réglées d'un coup.
    """
    from services.models import Artisan

    artisan = Artisan.objects.filter(user=tx.user).first()
    if not artisan:
        logger.error("Transaction %s : artisan introuvable", tx.reference)
        return

    periods = int((tx.raw_response or {}).get("periods", 1) or 1)
    days = settings.EAZYMARKET["ARTISAN_SUB_DAYS"] * periods
    artisan.activate_subscription(plan="pro", days=days)


def _add_shop_slots(tx):
    """Crédite un pack d'emplacements d'annonces à un vendeur."""
    from accounts.models import UserProfile

    profile = UserProfile.objects.filter(user=tx.user).first()
    if not profile:
        logger.error("Transaction %s : profil introuvable", tx.reference)
        return

    packs = int((tx.raw_response or {}).get("packs", 1) or 1)
    profile.extra_slots += settings.EAZYMARKET["SHOP_PACK_SIZE"] * packs
    profile.is_store_active = True
    profile.save(update_fields=["extra_slots", "is_store_active"])


def _add_video_slots(tx):
    """Crédite un pack d'emplacements vidéo."""
    from accounts.models import UserProfile

    profile = UserProfile.objects.filter(user=tx.user).first()
    if not profile:
        logger.error("Transaction %s : profil introuvable", tx.reference)
        return

    packs = int((tx.raw_response or {}).get("packs", 1) or 1)
    profile.extra_video_slots += settings.EAZYMARKET["VIDEO_PACK_SIZE"] * packs
    profile.save(update_fields=["extra_video_slots"])


def _unlock_contact(tx):
    """Ouvre l'accès au numéro d'un artisan pour ce client."""
    from services.models import Artisan, ContactUnlock

    artisan = Artisan.objects.filter(pk=tx.object_id).first()
    if not artisan:
        logger.error("Transaction %s : artisan %s introuvable", tx.reference, tx.object_id)
        return

    ContactUnlock.objects.update_or_create(
        client=tx.user,
        artisan=artisan,
        defaults={
            "amount": tx.amount,
            "is_free": False,
            "transaction_reference": tx.reference,
            "expires_at": timezone.now()
            + timedelta(days=settings.EAZYMARKET["CONTACT_UNLOCK_DAYS"]),
        },
    )
    Artisan.objects.filter(pk=artisan.pk).update(contact_views=artisan.contact_views + 1)


def _activate_boost(tx):
    from services.models import Artisan

    artisan = Artisan.objects.filter(user=tx.user).first()
    if artisan:
        artisan.is_featured = True
        artisan.featured_until = timezone.now() + timedelta(
            days=settings.EAZYMARKET["ARTISAN_BOOST_DAYS"]
        )
        artisan.save(update_fields=["is_featured", "featured_until"])


# ---------------------------------------------------------------------
# Portefeuilles
# ---------------------------------------------------------------------
def release_due_entries():
    """Libère les gains dont le délai de sécurité est écoulé.

    À lancer une fois par jour : python manage.py liberer_gains
    """
    now = timezone.now()
    qs = WalletEntry.objects.filter(is_released=False, release_at__lte=now)
    count = qs.update(is_released=True)
    if count:
        logger.info("%s écriture(s) de portefeuille libérée(s)", count)
    return count


def request_payout(user, amount=None):
    """Crée une demande de retrait. Retourne (payout|None, message)."""
    wallet = get_wallet(user)
    minimum = settings.EAZYMARKET["PAYOUT_MIN"]

    if not wallet.payout_number:
        return None, "Enregistrez d'abord votre numéro mobile money de retrait."

    amount = Decimal(int(amount)) if amount else wallet.available
    if amount <= 0:
        return None, "Aucun montant disponible."
    if amount < minimum:
        return None, f"Le retrait minimum est de {minimum:,.0f} FCFA.".replace(",", " ")
    if amount > wallet.available:
        return None, "Montant supérieur à votre solde disponible."
    if wallet.payouts.filter(status__in=[Payout.Status.REQUESTED, Payout.Status.PROCESSING]).exists():
        return None, "Une demande de retrait est déjà en cours."

    payout = Payout.objects.create(
        wallet=wallet,
        kind=Payout.Kind.WITHDRAWAL,
        amount=amount,
        channel=wallet.payout_channel,
        number=wallet.payout_number,
    )
    return payout, "Demande enregistrée. Le versement intervient sous 48 h ouvrées."


def demander_remboursement(user, montant=None, numero="", canal="", order=None):
    """Le client veut son argent sur son mobile money, pas un avoir.

    Même circuit que les retraits vendeurs : la demande apparaît dans
    l'administration, le versement se fait à la main, et le solde du client
    est débité au moment où il est réellement payé.

    Retourne (payout | None, message).
    """
    wallet = get_wallet(user)
    minimum = settings.EAZYMARKET["REFUND_MIN"]

    numero = (numero or wallet.payout_number or "").strip()
    if not numero:
        return None, "Indiquez le numéro mobile money sur lequel vous voulez être remboursé."

    # Cette vérification vient en premier : une demande en cours réserve
    # l'avoir, donc le solde disponible tombe à zéro. Vérifier le montant
    # avant renverrait « vous n'avez aucun avoir », ce qui est faux et
    # inquiétant pour quelqu'un qui attend justement son argent.
    en_cours = wallet.payouts.filter(
        kind=Payout.Kind.REFUND,
        status__in=[Payout.Status.REQUESTED, Payout.Status.PROCESSING],
    ).first()
    if en_cours:
        return None, (
            f"Une demande de remboursement est déjà en cours : "
            f"{en_cours.amount:,.0f} FCFA vers {en_cours.number}."
        ).replace(",", " ")

    montant = Decimal(int(montant)) if montant else wallet.available
    if montant <= 0:
        return None, "Vous n'avez aucun avoir à récupérer."
    if montant > wallet.available:
        return None, "Montant supérieur à votre avoir disponible."
    if montant < minimum:
        return None, (
            f"Le remboursement en argent démarre à {minimum:,.0f} FCFA — "
            "en dessous, les frais d'envoi coûteraient plus cher que la somme. "
            "Votre avoir reste utilisable sur n'importe quelle commande."
        ).replace(",", " ")

    canal = canal or wallet.payout_channel
    payout = Payout.objects.create(
        wallet=wallet,
        kind=Payout.Kind.REFUND,
        order=order,
        amount=montant,
        channel=canal,
        number=numero,
    )

    # On garde le numéro pour la prochaine fois.
    if not wallet.payout_number:
        wallet.payout_number = numero
        wallet.payout_channel = canal
        wallet.save(update_fields=["payout_number", "payout_channel"])

    logger.info("Remboursement demandé : %s (%s FCFA)", payout.reference, montant)
    return payout, (
        f"Demande enregistrée. Vos {montant:,.0f} FCFA seront envoyés sur {numero} "
        "sous 48 h ouvrées. Votre avoir reste bloqué jusque-là."
    ).replace(",", " ")
