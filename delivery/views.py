"""Dossier de validation des livreurs."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import DeliveryReferral, Sponsor


def _referral(user):
    referral, _ = DeliveryReferral.objects.get_or_create(deliverer=user)
    return referral


@login_required
def referral_dashboard(request):
    if not request.user.profile.can_deliver:
        return redirect("become_delivery")
    referral = _referral(request.user)
    return render(
        request,
        "delivery/referral_dashboard.html",
        {"referral": referral, "sponsors": referral.sponsors.all()},
    )


@login_required
@require_POST
def add_sponsor(request):
    if not request.user.profile.can_deliver:
        return redirect("become_delivery")
    referral = _referral(request.user)

    if referral.status == DeliveryReferral.Status.VERIFIED:
        messages.info(request, "Votre dossier est déjà validé.")
        return redirect("referral_dashboard")

    full_name = request.POST.get("full_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    if len(full_name) < 3 or len(phone) < 8:
        messages.error(request, "Indiquez un nom complet et un numéro joignable.")
    elif referral.sponsors.filter(phone=phone).exists():
        messages.error(request, "Ce numéro figure déjà dans votre dossier.")
    else:
        Sponsor.objects.create(
            referral=referral,
            full_name=full_name,
            phone=phone,
            relation=request.POST.get("relation", "").strip(),
        )
        messages.success(request, f"{full_name} ajouté à votre dossier.")
    return redirect("referral_dashboard")


@login_required
@require_POST
def remove_sponsor(request, sponsor_id):
    sponsor = get_object_or_404(Sponsor, id=sponsor_id, referral__deliverer=request.user)
    if sponsor.referral.status == DeliveryReferral.Status.VERIFIED:
        messages.error(request, "Un dossier validé ne peut plus être modifié.")
    else:
        sponsor.delete()
        messages.info(request, "Répondant retiré.")
    return redirect("referral_dashboard")


@login_required
@require_POST
def submit_referral(request):
    if not request.user.profile.can_deliver:
        return redirect("become_delivery")
    referral = _referral(request.user)

    if "id_document" in request.FILES:
        referral.id_document = request.FILES["id_document"]

    if not referral.is_complete:
        messages.error(
            request,
            f"Il vous manque encore {referral.missing} répondant"
            f"{'s' if referral.missing > 1 else ''}.",
        )
        referral.save()
        return redirect("referral_dashboard")

    referral.status = DeliveryReferral.Status.SUBMITTED
    from django.utils import timezone

    referral.submitted_at = timezone.now()
    referral.save()
    messages.success(
        request,
        "Dossier envoyé. Nous appelons vos répondants et vous activons sous 48 h.",
    )
    return redirect("referral_dashboard")


@staff_member_required
def referral_list(request):
    return render(
        request,
        "delivery/referral_list.html",
        {
            "submitted": DeliveryReferral.objects.filter(status="submitted").prefetch_related("sponsors"),
            "drafts": DeliveryReferral.objects.filter(status="draft"),
            "verified": DeliveryReferral.objects.filter(status="verified")[:20],
        },
    )


@staff_member_required
@require_POST
def verify_referral(request, referral_id):
    referral = get_object_or_404(DeliveryReferral, id=referral_id)
    action = request.POST.get("action")
    referral.note = request.POST.get("note", referral.note)

    if action == "approve":
        referral.mark_verified(by=request.user)
        messages.success(request, f"Livreur {referral.deliverer.username} validé.")
    elif action == "reject":
        referral.status = DeliveryReferral.Status.REJECTED
        referral.save()
        messages.warning(request, f"Dossier de {referral.deliverer.username} refusé.")

    try:
        from notifications.services import notifier

        notifier(
            referral.deliverer,
            "Dossier livreur" if action != "approve" else "Vous êtes validé !",
            "Votre dossier a été validé, vous pouvez accepter des courses."
            if action == "approve"
            else "Votre dossier n'a pas pu être validé. Contactez-nous pour en savoir plus.",
            lien="/livraison/mon-dossier/",
            urgent=True,
        )
    except Exception:  # noqa: BLE001
        pass
    return redirect("referral_list")


# ---------------------------------------------------------------------
# Annuaire public des livreurs
# ---------------------------------------------------------------------
def _livreurs_visibles(request):
    """Livreurs présentables au public : validés et dans le bon pays."""
    from accounts.models import UserProfile
    from regions.utils import current_country

    qs = (
        UserProfile.objects.filter(is_driver=True, is_verified=True)
        .select_related("user", "country")
    )
    pays = current_country(request)
    if pays:
        qs = qs.filter(models_Q_pays(pays))
    return qs


def models_Q_pays(pays):
    from django.db.models import Q
    return Q(country=pays) | Q(country__isnull=True)


def driver_list(request):
    """Annuaire public : trouver un livreur pour une livraison personnelle."""
    from django.core.paginator import Paginator
    from django.db.models import Case, When

    livreurs = _livreurs_visibles(request)

    query = request.GET.get("q", "").strip()
    if query:
        from django.db.models import Q
        livreurs = livreurs.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(delivery_zone__icontains=query)
            | Q(city__icontains=query)
            | Q(quartier__icontains=query)
        )

    # Les livreurs en ligne d'abord, puis les mieux notés.
    livreurs = livreurs.order_by(
        Case(When(is_available=True, then=0), default=1),
        "-delivery_rating", "-total_deliveries",
    )

    page = Paginator(livreurs, 12).get_page(request.GET.get("page"))
    return render(request, "delivery/driver_list.html", {
        "page_obj": page,
        "total": livreurs.count(),
        "query": query,
    })


def driver_detail(request, profile_id):
    from accounts.models import UserProfile

    livreur = get_object_or_404(
        UserProfile.objects.select_related("user", "country"),
        id=profile_id, is_driver=True, is_verified=True,
    )
    autres = (
        _livreurs_visibles(request)
        .exclude(id=livreur.id)
        .order_by("-delivery_rating")[:3]
    )
    return render(request, "delivery/driver_detail.html", {
        "livreur": livreur,
        "autres": autres,
        "peut_voir_contact": request.user.is_authenticated,
    })
