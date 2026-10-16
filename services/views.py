"""Place de marché des services : annuaire, demandes, devis, abonnements."""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from notifications.models import Notification
from videos.models import Video
from videos.services import emplacements
from notifications.services import notifier
from regions.utils import current_country
from payments.models import Transaction
from payments.services import start_transaction

from .models import (
    Artisan,
    ContactUnlock,
    Portfolio,
    Quote,
    ServiceCategory,
    ServiceMessage,
    ServiceRequest,
    ServiceReview,
)


def _notify(user, title, message, link="", urgent=False):
    """Notification interne. `urgent=True` envoie aussi un SMS.

    Beaucoup d'artisans n'ouvrent jamais leurs e-mails : pour une demande de
    client, c'est le SMS qui fait la différence entre un contrat et rien.
    """
    notifier(user, title, message, lien=link, urgent=urgent)


def _artisan_or_redirect(request):
    artisan = Artisan.objects.filter(user=request.user).first()
    if not artisan:
        messages.error(request, "Vous n'avez pas encore de profil professionnel.")
    return artisan


# ---------------------------------------------------------------------
# Annuaire public
# ---------------------------------------------------------------------
def services_home(request):
    country = current_country(request)
    categories = ServiceCategory.objects.annotate(
        n=Count(
            "artisans",
            filter=Q(artisans__is_available=True, artisans__is_blocked=False,
                     artisans__country=country),
        )
    )
    artisans = Artisan.objects.visible().in_country(country).select_related("service_category")
    return render(
        request,
        "services/services_home.html",
        {
            "categories": categories,
            "featured_artisans": artisans.filter(is_featured=True)[:6],
            "top_artisans": artisans.order_by("-rating", "-completed_jobs")[:8],
            "new_artisans": artisans.order_by("-created_at")[:4],
            "total_artisans": artisans.count(),
        },
    )


def artisan_list(request, category_slug=None):
    artisans = (
        Artisan.objects.visible()
        .in_country(current_country(request))
        .select_related("service_category")
    )
    category = None

    if category_slug:
        category = get_object_or_404(ServiceCategory, slug=category_slug)
        artisans = artisans.filter(
            Q(service_category=category) | Q(secondary_categories=category)
        ).distinct()

    query = request.GET.get("q", "").strip()
    if query:
        artisans = artisans.filter(
            Q(full_name__icontains=query)
            | Q(description__icontains=query)
            | Q(quartier__icontains=query)
            | Q(service_category__name__icontains=query)
        )

    quartier = request.GET.get("quartier", "").strip()
    if quartier:
        artisans = artisans.filter(
            Q(quartier__icontains=quartier) | Q(intervention_radius__icontains=quartier)
        )

    if request.GET.get("urgence"):
        artisans = artisans.filter(accepts_urgent=True)
    if request.GET.get("verifie"):
        artisans = artisans.filter(is_verified=True)

    sort = request.GET.get("tri", "recommande")
    artisans = artisans.order_by(
        {
            "recommande": "-is_featured",
            "note": "-rating",
            "experience": "-years_experience",
            "recent": "-created_at",
        }.get(sort, "-is_featured")
    )

    return render(
        request,
        "services/artisan_list.html",
        {
            "category": category,
            "categories": ServiceCategory.objects.all(),
            "page_obj": Paginator(artisans, 18).get_page(request.GET.get("page")),
            "query": query,
            "quartier": quartier,
            "sort": sort,
        },
    )


def artisan_detail(request, artisan_id):
    artisan = get_object_or_404(
        Artisan.objects.select_related("service_category"), id=artisan_id, is_blocked=False
    )
    can_review = False
    if request.user.is_authenticated:
        can_review = (
            ServiceRequest.objects.filter(
                artisan=artisan, client=request.user, status=ServiceRequest.Status.COMPLETED
            ).exists()
            and not ServiceReview.objects.filter(artisan=artisan, client=request.user).exists()
        )

    unlocked = ContactUnlock.is_unlocked(request.user, artisan)
    free_left = 0
    if request.user.is_authenticated:
        free_left = request.user.profile.free_unlocks_left

    return render(
        request,
        "services/artisan_detail.html",
        {
            "artisan": artisan,
            "videos": Video.pour(artisan),
            "portfolios": artisan.portfolios.all(),
            "reviews": artisan.reviews.select_related("client")[:10],
            "can_review": can_review,
            "unlocked": unlocked,
            "free_unlocks_left": free_left,
            "unlock_price": settings.EAZYMARKET["CONTACT_UNLOCK_PRICE"],
            "similar": Artisan.objects.visible()
            .in_country(artisan.country)
            .filter(service_category=artisan.service_category)
            .exclude(pk=artisan.pk)[:3],
        },
    )


@login_required
@require_POST
def unlock_contact(request, artisan_id):
    """Ouvre l'accès au numéro d'un artisan : crédit offert, sinon paiement."""
    artisan = get_object_or_404(Artisan, id=artisan_id, is_blocked=False)

    if ContactUnlock.is_unlocked(request.user, artisan):
        return redirect("artisan_detail", artisan_id=artisan.id)

    profile = request.user.profile
    price = settings.EAZYMARKET["CONTACT_UNLOCK_PRICE"]

    # Premier contact offert : on veut que le client essaie avant de payer
    if profile.free_unlocks_left > 0:
        ContactUnlock.objects.create(
            client=request.user,
            artisan=artisan,
            amount=0,
            is_free=True,
            expires_at=timezone.now()
            + timedelta(days=settings.EAZYMARKET["CONTACT_UNLOCK_DAYS"]),
        )
        profile.free_unlocks_left -= 1
        profile.save(update_fields=["free_unlocks_left"])
        Artisan.objects.filter(pk=artisan.pk).update(contact_views=artisan.contact_views + 1)
        messages.success(
            request,
            f"Contact débloqué — c'était votre contact offert. "
            f"Les suivants coûtent {price} FCFA.",
        )
        return redirect("artisan_detail", artisan_id=artisan.id)

    tx = start_transaction(
        user=request.user,
        purpose=Transaction.Purpose.CONTACT,
        amount=price,
        obj=artisan,
        payer_number=request.user.profile.phone,
    )
    return redirect("payment_pay", reference=tx.reference)


# ---------------------------------------------------------------------
# Demandes de service
# ---------------------------------------------------------------------
@login_required
def request_service(request, artisan_id):
    artisan = get_object_or_404(Artisan, id=artisan_id, is_blocked=False)

    if artisan.user == request.user:
        messages.error(request, "Vous ne pouvez pas vous adresser une demande à vous-même.")
        return redirect("artisan_detail", artisan_id=artisan.id)

    if not artisan.is_available:
        messages.warning(request, f"{artisan.full_name} n'accepte pas de nouvelle demande.")
        return redirect("artisan_detail", artisan_id=artisan.id)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        phone = request.POST.get("client_phone", "").strip()
        address = request.POST.get("client_address", "").strip()

        if not all([title, description, phone, address]):
            messages.error(request, "Merci de remplir tous les champs obligatoires.")
            return redirect("request_service", artisan_id=artisan.id)

        service_request = ServiceRequest.objects.create(
            artisan=artisan,
            client=request.user,
            title=title,
            description=description,
            client_phone=phone,
            client_address=address,
            preferred_date=request.POST.get("preferred_date") or None,
            preferred_time=request.POST.get("preferred_time") or None,
            urgency=request.POST.get("urgency", ServiceRequest.Urgency.FLEXIBLE),
            budget=request.POST.get("budget", "").strip(),
            photo=request.FILES.get("photo"),
        )

        _notify(
            artisan.user,
            "Nouvelle demande de service",
            f"{request.user.username} vous sollicite : {title}",
            "/services/mon-atelier/",
            urgent=True,
        )
        messages.success(
            request,
            f"Demande {service_request.reference} envoyée à {artisan.full_name}. "
            "Vous recevrez son devis dans votre espace.",
        )
        return redirect("service_request_detail", request_id=service_request.id)

    return render(
        request,
        "services/request_service.html",
        {"artisan": artisan, "profile": request.user.profile},
    )


@login_required
def my_service_requests(request):
    requests_qs = (
        ServiceRequest.objects.filter(client=request.user)
        .select_related("artisan")
        .prefetch_related("quotes")
    )
    return render(request, "services/my_requests.html", {"requests": requests_qs})


@login_required
def service_request_detail(request, request_id):
    """Fiche partagée entre le client et l'artisan : devis + messagerie."""
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related("artisan", "client"), id=request_id
    )
    is_client = service_request.client == request.user
    is_artisan = service_request.artisan.user == request.user
    if not (is_client or is_artisan or request.user.is_staff):
        messages.error(request, "Vous n'avez pas accès à cette demande.")
        return redirect("home")

    if is_artisan and not service_request.viewed_by_artisan:
        service_request.viewed_by_artisan = True
        service_request.save(update_fields=["viewed_by_artisan"])

    service_request.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)

    return render(
        request,
        "services/request_detail.html",
        {
            "sr": service_request,
            "is_client": is_client,
            "is_artisan": is_artisan,
            "quotes": service_request.quotes.all(),
            "thread": service_request.messages.select_related("sender"),
        },
    )


@login_required
@require_POST
def post_message(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    if request.user not in (service_request.client, service_request.artisan.user):
        messages.error(request, "Accès refusé.")
        return redirect("home")

    body = request.POST.get("body", "").strip()
    if body:
        ServiceMessage.objects.create(
            service_request=service_request,
            sender=request.user,
            body=body,
            attachment=request.FILES.get("attachment"),
        )
        other = (
            service_request.artisan.user
            if request.user == service_request.client
            else service_request.client
        )
        _notify(
            other,
            f"Nouveau message — {service_request.reference}",
            body[:120],
            f"/services/demande/{service_request.id}/",
        )
    return redirect("service_request_detail", request_id=service_request.id)


# ---------------------------------------------------------------------
# Devis
# ---------------------------------------------------------------------
@login_required
@require_POST
def create_quote(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    artisan = service_request.artisan
    if artisan.user != request.user:
        messages.error(request, "Seul l'artisan concerné peut envoyer un devis.")
        return redirect("home")

    if not artisan.can_answer:
        messages.warning(
            request,
            "Votre abonnement a expiré. Réactivez-le pour continuer à envoyer des devis.",
        )
        return redirect("subscribe_artisan")

    def money(field):
        raw = (request.POST.get(field) or "0").replace(" ", "")
        return int(raw) if raw.isdigit() else 0

    quote = Quote.objects.create(
        service_request=service_request,
        artisan=artisan,
        labour_cost=money("labour_cost"),
        materials_cost=money("materials_cost"),
        travel_cost=money("travel_cost"),
        details=request.POST.get("details", "").strip(),
        duration=request.POST.get("duration", "").strip(),
        valid_until=request.POST.get("valid_until") or None,
    )
    service_request.status = ServiceRequest.Status.QUOTED
    service_request.save(update_fields=["status"])

    _notify(
        service_request.client,
        "Vous avez reçu un devis",
        f"{artisan.full_name} propose {quote.total:,.0f} FCFA pour « {service_request.title} »".replace(",", " "),
        f"/services/demande/{service_request.id}/",
        urgent=True,
    )
    messages.success(request, f"Devis {quote.reference} envoyé au client.")
    return redirect("service_request_detail", request_id=service_request.id)


@login_required
@require_POST
def respond_quote(request, quote_id, action):
    quote = get_object_or_404(Quote, id=quote_id)
    service_request = quote.service_request
    if service_request.client != request.user:
        messages.error(request, "Accès refusé.")
        return redirect("home")

    quote.client_message = request.POST.get("client_message", "").strip()
    quote.responded_at = timezone.now()

    if action == "accepter":
        quote.status = Quote.Status.ACCEPTED
        service_request.status = ServiceRequest.Status.ACCEPTED
        service_request.save(update_fields=["status"])
        service_request.quotes.exclude(pk=quote.pk).update(status=Quote.Status.REFUSED)
        _notify(
            service_request.artisan.user,
            "Devis accepté",
            f"{request.user.username} a accepté votre devis {quote.reference}.",
            f"/services/demande/{service_request.id}/",
            urgent=True,
        )
        messages.success(request, "Devis accepté. Convenez du rendez-vous dans la discussion.")
    else:
        quote.status = Quote.Status.REFUSED
        _notify(
            service_request.artisan.user,
            "Devis refusé",
            f"Le devis {quote.reference} n'a pas été retenu.",
            f"/services/demande/{service_request.id}/",
        )
        messages.info(request, "Devis refusé.")

    quote.save(update_fields=["status", "client_message", "responded_at"])
    return redirect("service_request_detail", request_id=service_request.id)


# ---------------------------------------------------------------------
# Espace artisan
# ---------------------------------------------------------------------
@login_required
def artisan_dashboard(request):
    artisan = _artisan_or_redirect(request)
    if not artisan:
        return redirect("register_artisan")

    artisan.is_subscription_active()
    requests_qs = artisan.service_requests.select_related("client")

    return render(
        request,
        "services/artisan_dashboard.html",
        {
            "artisan": artisan,
            "pending_list": requests_qs.filter(status=ServiceRequest.Status.PENDING)[:10],
            "active_list": requests_qs.filter(
                status__in=[
                    ServiceRequest.Status.QUOTED,
                    ServiceRequest.Status.ACCEPTED,
                    ServiceRequest.Status.IN_PROGRESS,
                ]
            )[:10],
            "stats": {
                "total": requests_qs.count(),
                "pending": requests_qs.filter(status=ServiceRequest.Status.PENDING).count(),
                "completed": requests_qs.filter(status=ServiceRequest.Status.COMPLETED).count(),
                "quotes": artisan.quotes.count(),
                "accepted_quotes": artisan.quotes.filter(status=Quote.Status.ACCEPTED).count(),
            },
            "portfolios": artisan.portfolios.all(),
            "mes_videos": Video.toutes_pour(artisan),
            "video": emplacements(request.user),
        },
    )


@login_required
@require_POST
def manage_service_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    if service_request.artisan.user != request.user:
        messages.error(request, "Accès refusé.")
        return redirect("artisan_dashboard")

    action = request.POST.get("action")
    note = request.POST.get("admin_message", "").strip()
    mapping = {
        "accept": (ServiceRequest.Status.ACCEPTED, "Demande acceptée", "a accepté votre demande"),
        "start": (ServiceRequest.Status.IN_PROGRESS, "Travail démarré", "a démarré le travail"),
        "reject": (ServiceRequest.Status.REJECTED, "Demande refusée", "a refusé votre demande"),
        "complete": (ServiceRequest.Status.COMPLETED, "Travail terminé", "a marqué le travail comme terminé"),
        "cancel": (ServiceRequest.Status.CANCELLED, "Demande annulée", "a annulé la demande"),
    }
    if action not in mapping:
        return redirect("artisan_dashboard")

    status, title, phrase = mapping[action]
    service_request.status = status
    service_request.admin_message = note
    service_request.save(update_fields=["status", "admin_message"])

    if status == ServiceRequest.Status.COMPLETED:
        artisan = service_request.artisan
        artisan.completed_jobs += 1
        artisan.save(update_fields=["completed_jobs"])

    _notify(
        service_request.client,
        title,
        f"{service_request.artisan.full_name} {phrase} : {service_request.title}",
        f"/services/demande/{service_request.id}/",
    )
    messages.success(request, title)
    return redirect(request.META.get("HTTP_REFERER", "artisan_dashboard"))


@login_required
def register_artisan(request):
    if Artisan.objects.filter(user=request.user).exists():
        return redirect("artisan_dashboard")

    if request.method == "POST":
        required = ["full_name", "service_category", "phone", "address", "quartier", "description", "price_range"]
        data = {f: request.POST.get(f, "").strip() for f in required}
        if any(not v for v in data.values()):
            messages.error(request, "Merci de remplir tous les champs obligatoires.")
            return redirect("register_artisan")

        category = get_object_or_404(ServiceCategory, id=data["service_category"])
        years = request.POST.get("years_experience", "0")

        artisan = Artisan.objects.create(
            user=request.user,
            full_name=data["full_name"],
            service_category=category,
            phone=data["phone"],
            whatsapp=request.POST.get("whatsapp", "").strip(),
            email=request.POST.get("email", "").strip(),
            address=data["address"],
            quartier=data["quartier"],
            city=request.POST.get("city", "Ouagadougou").strip() or "Ouagadougou",
            intervention_radius=request.POST.get("intervention_radius", "").strip(),
            description=data["description"],
            years_experience=int(years) if years.isdigit() else 0,
            price_range=data["price_range"],
            accepts_urgent=bool(request.POST.get("accepts_urgent")),
            photo=request.FILES.get("photo"),
        )

        # Photos de réalisations envoyées dès l'inscription
        works = request.FILES.getlist("works")
        titles = request.POST.getlist("work_title")
        for index, image in enumerate(works[:6]):
            Portfolio.objects.create(
                artisan=artisan,
                title=(titles[index].strip() if index < len(titles) and titles[index].strip()
                       else f"Réalisation {index + 1}"),
                image=image,
            )

        profile = request.user.profile
        profile.user_type = "artisan"
        profile.phone = artisan.phone
        profile.address = artisan.address
        profile.quartier = artisan.quartier
        profile.save()

        if settings.EAZYMARKET.get("ARTISAN_FREE_LAUNCH"):
            messages.success(
                request,
                f"Bienvenue {artisan.full_name} ! Votre profil est en ligne — "
                "l'inscription est offerte pendant la période de lancement.",
            )
            return redirect("artisan_dashboard")

        messages.success(
            request,
            f"Bienvenue {artisan.full_name} ! Votre profil est créé. "
            "Dernière étape : activez-le pour apparaître dans les recherches.",
        )
        return redirect("subscribe_artisan")

    return render(
        request,
        "services/register_artisan.html",
        {"categories": ServiceCategory.objects.all()},
    )


@login_required
@require_POST
def add_portfolio(request):
    artisan = _artisan_or_redirect(request)
    if not artisan:
        return redirect("register_artisan")
    title = request.POST.get("title", "").strip()
    if title:
        Portfolio.objects.create(
            artisan=artisan,
            title=title,
            description=request.POST.get("description", "").strip(),
            image=request.FILES.get("image"),
            image_url=request.POST.get("image_url", "").strip(),
        )
        messages.success(request, "Réalisation ajoutée à votre portfolio.")
    return redirect("artisan_dashboard")


@login_required
@require_POST
def toggle_availability(request):
    artisan = _artisan_or_redirect(request)
    if artisan:
        artisan.is_available = not artisan.is_available
        artisan.save(update_fields=["is_available"])
        messages.success(
            request,
            "Vous êtes visible et disponible." if artisan.is_available else "Vous êtes en pause.",
        )
    return redirect("artisan_dashboard")


# ---------------------------------------------------------------------
# Abonnement
# ---------------------------------------------------------------------
@login_required
def subscribe_artisan(request):
    """Activation et renouvellement de l'abonnement artisan."""
    artisan = _artisan_or_redirect(request)
    if not artisan:
        return redirect("register_artisan")

    conf = settings.EAZYMARKET
    price = conf["ARTISAN_SUB_PRICE"]
    days = conf["ARTISAN_SUB_DAYS"]

    if request.method == "POST":
        periods = request.POST.get("periods", "1")
        periods = int(periods) if periods.isdigit() and 1 <= int(periods) <= 6 else 1

        tx = start_transaction(
            user=request.user,
            purpose=Transaction.Purpose.SUBSCRIPTION,
            amount=price * periods,
            payer_number=artisan.phone,
            obj=artisan,
        )
        tx.raw_response = {"periods": periods}
        tx.save(update_fields=["raw_response"])
        return redirect("payment_pay", reference=tx.reference)

    return render(
        request,
        "services/subscribe.html",
        {
            "artisan": artisan,
            "price": price,
            "days": days,
            "months": round(days / 30),
            "free_launch": conf.get("ARTISAN_FREE_LAUNCH"),
            "options": [
                {"periods": 1, "amount": price, "label": f"{round(days/30)} mois"},
                {"periods": 3, "amount": price * 3, "label": f"{round(days*3/30)} mois"},
                {"periods": 6, "amount": price * 6, "label": "1 an"},
            ],
        },
    )


@login_required
@require_POST
def boost_artisan(request):
    """Mise en avant en page d'accueil pendant quelques jours."""
    artisan = _artisan_or_redirect(request)
    if not artisan:
        return redirect("register_artisan")

    tx = start_transaction(
        user=request.user,
        purpose=Transaction.Purpose.BOOST,
        amount=settings.EAZYMARKET["ARTISAN_BOOST_PRICE"],
        payer_number=artisan.phone,
        obj=artisan,
    )
    return redirect("payment_pay", reference=tx.reference)


# ---------------------------------------------------------------------
# Avis
# ---------------------------------------------------------------------
@login_required
def leave_review(request, artisan_id):
    artisan = get_object_or_404(Artisan, id=artisan_id)
    completed = ServiceRequest.objects.filter(
        artisan=artisan, client=request.user, status=ServiceRequest.Status.COMPLETED
    ).first()

    if not completed:
        messages.error(request, "Vous pouvez noter un artisan après un travail terminé.")
        return redirect("artisan_detail", artisan_id=artisan.id)
    if ServiceReview.objects.filter(artisan=artisan, client=request.user).exists():
        messages.info(request, "Vous avez déjà laissé un avis pour cet artisan.")
        return redirect("artisan_detail", artisan_id=artisan.id)

    if request.method == "POST":
        rating = int(request.POST.get("rating", 0) or 0)
        comment = request.POST.get("comment", "").strip()
        if not (1 <= rating <= 5) or len(comment) < 5:
            messages.error(request, "Choisissez une note et écrivez quelques mots.")
            return redirect("leave_review", artisan_id=artisan.id)

        def sub(field):
            value = request.POST.get(field)
            return int(value) if value and value.isdigit() else None

        ServiceReview.objects.create(
            artisan=artisan,
            client=request.user,
            service_request=completed,
            rating=rating,
            punctuality=sub("punctuality"),
            quality=sub("quality"),
            comment=comment,
        )
        _notify(artisan.user, "Nouvel avis", f"{request.user.username} vous a noté {rating}/5.")
        messages.success(request, "Merci pour votre avis !")
        return redirect("artisan_detail", artisan_id=artisan.id)

    return render(request, "services/leave_review.html", {"artisan": artisan})


@login_required
@require_POST
def reply_review(request, review_id):
    review = get_object_or_404(ServiceReview, id=review_id)
    if review.artisan.user != request.user:
        messages.error(request, "Accès refusé.")
        return redirect("home")
    review.artisan_reply = request.POST.get("reply", "").strip()
    review.save(update_fields=["artisan_reply"])
    messages.success(request, "Réponse publiée.")
    return redirect("artisan_detail", artisan_id=review.artisan_id)
