"""Ajout, suppression et achat d'emplacements vidéo."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from payments.models import Transaction
from payments.services import start_transaction
from products.models import Product
from services.models import Artisan

from .models import Video
from .services import ajouter_video, emplacements


def _cible_et_retour(request):
    """Retrouve l'objet auquel rattacher la vidéo, et où renvoyer ensuite.

    On ne se fie pas au champ caché : on vérifie que l'objet appartient bien
    à la personne connectée.
    """
    genre = request.POST.get("cible")

    if genre == "produit":
        produit = get_object_or_404(
            Product, id=request.POST.get("produit_id"), seller=request.user
        )
        return produit, redirect("seller_dashboard")

    if genre == "artisan":
        artisan = get_object_or_404(Artisan, user=request.user)
        return artisan, redirect("artisan_dashboard")

    return None, redirect("home")


@login_required
@require_POST
def add_video(request):
    cible, retour = _cible_et_retour(request)
    if cible is None:
        messages.error(request, "Impossible de savoir à quoi rattacher cette vidéo.")
        return retour

    try:
        ajouter_video(
            request.user,
            cible,
            fichier=request.FILES.get("file"),
            lien=request.POST.get("external_url", ""),
            titre=request.POST.get("title", ""),
        )
    except ValidationError as erreur:
        messages.error(request, " ".join(erreur.messages))
        return retour

    messages.success(
        request,
        "Vidéo en ligne. Les fiches qui montrent une vidéo sont nettement plus "
        "consultées : c'est ce qui rassure un client qui paie d'avance.",
    )
    return retour


@login_required
@require_POST
def delete_video(request, video_id):
    video = get_object_or_404(Video, id=video_id, owner=request.user)
    hebergee = video.is_hosted
    video.delete()
    messages.info(
        request,
        "Vidéo supprimée. L'emplacement est de nouveau libre."
        if hebergee else "Lien vidéo retiré.",
    )
    return redirect(request.META.get("HTTP_REFERER", "seller_dashboard"))


@login_required
def buy_video_slots(request):
    """Achat d'un pack d'emplacements vidéo."""
    conf = settings.EAZYMARKET
    etat = emplacements(request.user)

    if etat["illimite"]:
        messages.info(request, "Votre compte n'a aucune limite de vidéos.")
        return redirect("seller_dashboard")

    if request.method == "POST":
        packs = request.POST.get("packs", "1")
        packs = int(packs) if packs.isdigit() and 1 <= int(packs) <= 10 else 1

        tx = start_transaction(
            user=request.user,
            purpose=Transaction.Purpose.VIDEO_PACK,
            amount=conf["VIDEO_PACK_PRICE"] * packs,
            payer_number=getattr(request.user.profile, "phone", ""),
            obj=request.user.profile,
        )
        tx.raw_response = {"packs": packs}
        tx.save(update_fields=["raw_response"])
        return redirect("payment_pay", reference=tx.reference)

    return render(
        request,
        "videos/buy_video_slots.html",
        {
            "etat": etat,
            "pack_size": conf["VIDEO_PACK_SIZE"],
            "pack_price": conf["VIDEO_PACK_PRICE"],
            "options": [
                {"packs": n, "slots": conf["VIDEO_PACK_SIZE"] * n,
                 "amount": conf["VIDEO_PACK_PRICE"] * n}
                for n in (1, 2, 4)
            ],
        },
    )
