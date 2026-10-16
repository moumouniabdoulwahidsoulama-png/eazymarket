"""Comptes, tableaux de bord vendeur / livreur / administrateur."""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from django.conf import settings

from django.contrib.contenttypes.models import ContentType

from orders.models import Order, OrderItem, SellerConfirmation
from videos.models import Video
from videos.services import emplacements
from payments.models import Payout, Transaction
from payments.services import get_wallet, start_transaction
from products.models import Category, Product
from regions.utils import current_country
from services.models import Artisan, ServiceRequest

from .forms import ProfileForm, UserRegistrationForm
from .models import UserProfile


def _dashboard_redirect(user):
    return redirect(user.profile.dashboard_url_name)


# ---------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------
ROLE_LABELS = {
    "buyer": ("Créer mon compte", "Achetez et trouvez un professionnel près de chez vous."),
    "seller": ("Ouvrir ma boutique", "Publiez vos produits et vendez à toute la ville."),
    "delivery": ("Devenir livreur", "Prenez les courses qui vous arrangent, quand vous voulez."),
    "artisan": ("Proposer mes services", "Recevez des demandes de clients de votre quartier."),
}


def register(request):
    """Inscription. Le rôle peut être présélectionné : /compte/inscription/?role=delivery"""
    if request.user.is_authenticated:
        # Déjà un compte : on n'en crée pas un second, on ajoute l'activité.
        role = request.GET.get("role")
        if role == "delivery":
            return redirect("become_delivery")
        if role == "seller":
            return redirect("become_seller")
        if role == "artisan":
            return redirect("register_artisan")
        return redirect("profile")

    role = request.GET.get("role") or request.POST.get("user_type") or "buyer"
    if role not in ROLE_LABELS:
        role = "buyer"

    form = UserRegistrationForm(
        request.POST or None, initial_country=current_country(request)
    )
    if request.method != "POST":
        form.fields["user_type"].initial = role
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        role = user.profile.user_type

        if role == UserProfile.Type.ARTISAN:
            messages.success(
                request,
                f"Bienvenue {user.username} ! Décrivez maintenant votre métier "
                "et ajoutez des photos de vos réalisations.",
            )
            return redirect("register_artisan")

        if role == UserProfile.Type.DELIVERY:
            from delivery.models import DeliveryReferral

            DeliveryReferral.objects.get_or_create(deliverer=user)
            messages.success(
                request,
                f"Bienvenue {user.username} ! Dernière étape : partagez le lien de "
                f"l'application à {settings.EAZYMARKET['DELIVERY_REQUIRED_SHARES']} personnes "
                "pour activer votre compte livreur.",
            )
            return redirect("referral_dashboard")

        messages.success(request, f"Bienvenue {user.username} ! Votre compte est prêt.")
        return _dashboard_redirect(user)

    title, intro = ROLE_LABELS[role]
    return render(
        request,
        "accounts/register.html",
        {"form": form, "preselected_role": role, "page_title": title, "page_intro": intro},
    )


# ---------------------------------------------------------------------
# Ajouter une activité à un compte existant
# ---------------------------------------------------------------------
@login_required
def become_seller(request):
    """Un compte existant ouvre sa boutique — sans créer un second compte."""
    profile_obj = request.user.profile

    if profile_obj.can_sell:
        return redirect("seller_dashboard")

    # Fiche déjà remplie mais pack non réglé : on ne redemande pas les
    # informations, on renvoie directement au paiement.
    if profile_obj.boutique_en_attente and request.method != "POST":
        messages.info(
            request,
            "Il ne manque que le règlement pour ouvrir votre boutique.",
        )
        return redirect("buy_slots")

    if request.method == "POST":
        store_name = request.POST.get("store_name", "").strip()
        phone = request.POST.get("phone", "").strip() or profile_obj.phone
        if len(store_name) < 2:
            messages.error(request, "Donnez un nom à votre boutique.")
            return redirect("become_seller")

        profile_obj.store_name = store_name
        profile_obj.store_description = request.POST.get("store_description", "").strip()
        profile_obj.phone = phone
        profile_obj.quartier = request.POST.get("quartier", "").strip() or profile_obj.quartier
        # La boutique n'est PAS ouverte ici : elle s'ouvre au paiement du pack
        # (payments.services._add_shop_slots met is_store_active à True).
        if profile_obj.user_type == UserProfile.Type.BUYER:
            profile_obj.user_type = UserProfile.Type.SELLER
        profile_obj.save()

        conf = settings.EAZYMARKET
        messages.success(
            request,
            f"« {store_name} » est enregistrée. Dernière étape : le pack de "
            f"{conf['SHOP_PACK_SIZE']} annonces à {conf['SHOP_PACK_PRICE']:,.0f} FCFA, "
            "qui ouvre votre boutique.".replace(",", " "),
        )
        return redirect("buy_slots")

    return render(request, "accounts/become_seller.html", {"profile": profile_obj})


@login_required
def become_delivery(request):
    """Un compte existant devient livreur — sans créer un second compte."""
    profile_obj = request.user.profile

    if profile_obj.can_deliver:
        return redirect("referral_dashboard")

    if request.method == "POST":
        vehicle = request.POST.get("vehicle_type", "").strip()
        zone = request.POST.get("delivery_zone", "").strip()
        phone = request.POST.get("phone", "").strip() or profile_obj.phone

        if not vehicle or not zone or not phone:
            messages.error(request, "Indiquez votre moyen de transport, votre zone et votre téléphone.")
            return redirect("become_delivery")

        profile_obj.vehicle_type = vehicle
        profile_obj.delivery_zone = zone
        profile_obj.phone = phone
        profile_obj.is_driver = True
        profile_obj.is_available = False  # activé après validation du dossier
        if profile_obj.user_type == UserProfile.Type.BUYER:
            profile_obj.user_type = UserProfile.Type.DELIVERY
        profile_obj.save()

        from delivery.models import DeliveryReferral

        DeliveryReferral.objects.get_or_create(deliverer=request.user)

        messages.success(
            request,
            "Compte livreur créé. Dernière étape : partagez le lien de l'application "
            f"à {settings.EAZYMARKET['DELIVERY_REQUIRED_SHARES']} personnes pour être activé.",
        )
        return redirect("referral_dashboard")

    return render(
        request,
        "accounts/become_delivery.html",
        {"profile": profile_obj, "vehicles": UserProfile.VEHICLES},
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    from . import securite

    if request.method == "POST":
        # Barrière anti-force-brute : au bout de 5 échecs récents d'une même
        # IP, on refuse même les bons mots de passe pendant un moment.
        bloque, minutes = securite.est_bloque(request)
        if bloque:
            messages.error(
                request,
                f"Trop de tentatives. Réessayez dans {minutes} minute"
                f"{'s' if minutes > 1 else ''}, ou réinitialisez votre mot de passe.",
            )
            return render(request, "accounts/login.html",
                          {"next": request.POST.get("next", "")})

        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # On accepte l'e-mail comme identifiant
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).first()
            identifier = match.username if match else identifier

        user = authenticate(request, username=identifier, password=password)

        if user is None:
            securite.journaliser(request, identifier, succes=False)
            restants = securite.MAX_ECHECS - securite.echecs_recents(securite.adresse_ip(request))
            if 0 < restants <= 2:
                messages.error(
                    request,
                    f"Identifiant ou mot de passe incorrect. "
                    f"Encore {restants} essai{'s' if restants > 1 else ''} avant blocage.",
                )
            else:
                messages.error(request, "Identifiant ou mot de passe incorrect.")
            return render(request, "accounts/login.html",
                          {"next": request.POST.get("next", "")})

        # Mot de passe bon. Double authentification demandée ?
        profil = getattr(user, "profile", None)
        if profil and profil.two_factor_enabled:
            envoi = securite.envoyer_code(user)
            if envoi:
                empreinte, expiration, canal = envoi
                request.session["2fa"] = {
                    "user_id": user.id,
                    "empreinte": empreinte,
                    "expiration": expiration,
                    "canal": canal,
                    "next": request.POST.get("next") or request.GET.get("next") or "",
                }
                request.session.set_expiry(600)  # 10 min pour saisir le code
                return redirect("login_verify")
            # Aucun canal d'envoi : on ne bloque pas l'utilisateur dehors,
            # on le connecte et on l'avertit.
            messages.warning(
                request,
                "Impossible de vous envoyer le code de connexion. "
                "Vérifiez votre e-mail dans votre profil.",
            )

        securite.journaliser(request, identifier, succes=True, utilisateur=user)
        login(request, user)
        messages.success(request, f"Content de vous revoir, {user.username} !")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return _dashboard_redirect(user)

    return render(request, "accounts/login.html", {"next": request.GET.get("next", "")})


def login_verify_view(request):
    """Deuxième étape : le code à usage unique."""
    from . import securite

    donnees = request.session.get("2fa")
    if not donnees:
        return redirect("login")

    user = User.objects.filter(id=donnees["user_id"]).first()
    if not user:
        request.session.pop("2fa", None)
        return redirect("login")

    canal_libelle = "votre e-mail" if donnees["canal"] == "email" else "SMS"

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "renvoyer":
            envoi = securite.envoyer_code(user)
            if envoi:
                empreinte, expiration, canal = envoi
                donnees.update(empreinte=empreinte, expiration=expiration, canal=canal)
                request.session["2fa"] = donnees
                messages.info(request, "Un nouveau code vous a été envoyé.")
            return render(request, "accounts/login_verify.html", {"canal": canal_libelle})

        code = request.POST.get("code", "")
        if securite.code_valide(code, donnees["empreinte"], donnees["expiration"]):
            next_url = donnees.get("next")
            request.session.pop("2fa", None)
            securite.journaliser(request, user.username, succes=True, utilisateur=user)
            login(request, user)
            messages.success(request, f"Content de vous revoir, {user.username} !")
            return redirect(next_url) if next_url else _dashboard_redirect(user)

        securite.journaliser(request, user.username, succes=False, utilisateur=user)
        messages.error(request, "Code incorrect ou expiré.")

    return render(request, "accounts/login_verify.html", {"canal": canal_libelle})


@login_required
def security_settings(request):
    """Le compte : activer/désactiver la double authentification."""
    from . import securite

    profil = request.user.profile

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "activer":
            canal = request.POST.get("canal", "email")
            if canal == "email" and not request.user.email:
                messages.error(
                    request,
                    "Ajoutez d'abord une adresse e-mail à votre profil pour "
                    "recevoir les codes.",
                )
                return redirect("security_settings")
            if canal == "sms" and not (profil.whatsapp or profil.phone):
                messages.error(request, "Ajoutez d'abord un numéro à votre profil.")
                return redirect("security_settings")
            profil.two_factor_channel = canal
            profil.two_factor_enabled = True
            profil.save(update_fields=["two_factor_channel", "two_factor_enabled"])
            messages.success(
                request,
                "Double authentification activée. Un code vous sera demandé "
                "à chaque connexion.",
            )
        elif action == "desactiver":
            profil.two_factor_enabled = False
            profil.save(update_fields=["two_factor_enabled"])
            messages.info(request, "Double authentification désactivée.")

        return redirect("security_settings")

    connexions = request.user.connexions.all()[:10]
    return render(request, "accounts/security_settings.html", {
        "profil": profil,
        "connexions": connexions,
        "a_email": bool(request.user.email),
        "a_numero": bool(profil.whatsapp or profil.phone),
    })


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté. À bientôt !")
    return redirect("home")


@login_required
def profile(request):
    profile_obj = request.user.profile
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile_obj)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile_obj,
            "form": form,
            "orders": Order.objects.filter(user=request.user)[:5],
            "requests": ServiceRequest.objects.filter(client=request.user)[:5],
        },
    )


# ---------------------------------------------------------------------
# Vendeur
# ---------------------------------------------------------------------
@login_required
def seller_dashboard(request):
    profile_obj = request.user.profile
    if not profile_obj.can_sell:
        return redirect("become_seller")

    products = list(Product.objects.filter(seller=request.user).select_related("category"))

    # Les vidéos de toutes les annonces en une seule requête, puis accrochées
    # à chaque produit : le tableau de bord d'un vendeur bien fourni ne doit
    # pas déclencher une requête par ligne.
    type_produit = ContentType.objects.get_for_model(Product)
    par_produit = {}
    for video in Video.objects.filter(
        content_type=type_produit, object_id__in=[p.id for p in products]
    ):
        par_produit.setdefault(video.object_id, []).append(video)
    for produit in products:
        produit.mes_videos = par_produit.get(produit.id, [])

    items = OrderItem.objects.filter(seller=request.user).select_related("order")
    paid_items = items.filter(order__is_paid=True)

    revenue = paid_items.aggregate(t=Sum("subtotal"))["t"] or Decimal("0")
    commission = paid_items.aggregate(t=Sum("commission"))["t"] or Decimal("0")
    last_30 = paid_items.filter(order__created_at__gte=timezone.now() - timedelta(days=30))

    return render(
        request,
        "accounts/seller_dashboard.html",
        {
            "products": products,
            "video": emplacements(request.user),
            "categories": Category.objects.all(),
            "wallet": get_wallet(request.user),
            "shop": {
                "unlimited": profile_obj.has_unlimited_slots,
                "official": profile_obj.is_official or request.user.is_staff,
                "used": profile_obj.used_slots,
                "total": profile_obj.total_slots,
                "left": profile_obj.slots_left,
                "free": settings.EAZYMARKET["SHOP_FREE_SLOTS"],
                "pack_size": settings.EAZYMARKET["SHOP_PACK_SIZE"],
                "pack_price": settings.EAZYMARKET["SHOP_PACK_PRICE"],
            },
            "stats": {
                "products": len(products),
                "out_of_stock": sum(1 for p in products if not p.stock),
                "orders": paid_items.values("order").distinct().count(),
                "revenue": revenue,
                "commission": commission,
                "net": revenue - commission,
                "month_revenue": last_30.aggregate(t=Sum("subtotal"))["t"] or 0,
                "views": sum(p.views_count for p in products),
            },
            "recent_items": items.order_by("-created_at")[:8],
            "profile": profile_obj,
            "a_confirmer": SellerConfirmation.objects.filter(
                seller=request.user, status=SellerConfirmation.Status.PENDING
            ).select_related("order").order_by("deadline"),
        },
    )


@login_required
@require_POST
def add_product(request):
    profile_obj = request.user.profile
    if not profile_obj.can_sell:
        return redirect("become_seller")
    if not profile_obj.can_publish:
        messages.warning(
            request,
            f"Vos {profile_obj.total_slots} emplacements sont occupés. "
            f"Achetez un pack de {settings.EAZYMARKET['SHOP_PACK_SIZE']} annonces "
            f"pour agrandir votre boutique.",
        )
        return redirect("buy_slots")

    name = request.POST.get("name", "").strip()
    price = request.POST.get("base_price", "").strip()
    category_id = request.POST.get("category")
    description = request.POST.get("description", "").strip()

    if not (name and price.isdigit() and category_id and description):
        messages.error(request, "Nom, catégorie, prix et description sont obligatoires.")
        return redirect("seller_dashboard")

    is_official = profile_obj.is_official or request.user.is_staff
    product = Product.objects.create(
        commission_rate=Decimal("0") if is_official else Decimal(str(settings.EAZYMARKET["COMMISSION_RATE"])),
        name=name,
        description=description,
        short_description=request.POST.get("short_description", "").strip()[:300],
        base_price=int(price),
        stock=int(request.POST.get("stock", 1) or 1),
        category=get_object_or_404(Category, id=category_id),
        seller=request.user,
        condition=request.POST.get("condition", Product.Condition.NEW),
        main_image=request.FILES.get("main_image"),
        warranty_months=int(request.POST.get("warranty_months", 0) or 0),
        made_to_order=bool(request.POST.get("made_to_order")),
        lead_time_days=max(1, min(30, int(request.POST.get("lead_time_days", 2) or 2))),
    )
    if is_official:
        messages.success(
            request,
            f"« {product.name} » est en ligne à {product.price:,.0f} FCFA "
            "(boutique officielle : aucune commission).".replace(",", " "),
        )
    else:
        messages.success(
            request,
            f"« {product.name} » est en ligne à {product.price:,.0f} FCFA "
            f"(vous touchez {product.base_price:,.0f} FCFA).".replace(",", " "),
        )
    return redirect("seller_dashboard")


@login_required
def buy_slots(request):
    """Achat d'un pack d'emplacements — c'est lui qui ouvre la boutique.

    Accessible avant l'ouverture : le vendeur qui vient de remplir sa fiche
    arrive ici pour payer. Exiger `can_sell` renverrait en boucle vers le
    formulaire, qui renvoie ici.
    """
    profile_obj = request.user.profile
    if not (profile_obj.can_sell or profile_obj.boutique_en_attente):
        return redirect("become_seller")

    conf = settings.EAZYMARKET

    if profile_obj.has_unlimited_slots:
        messages.info(request, "Votre boutique n'a aucune limite d'annonces.")
        return redirect("seller_dashboard")

    if request.method == "POST":
        packs = request.POST.get("packs", "1")
        packs = int(packs) if packs.isdigit() and 1 <= int(packs) <= 10 else 1

        tx = start_transaction(
            user=request.user,
            purpose=Transaction.Purpose.SHOP_PACK,
            amount=conf["SHOP_PACK_PRICE"] * packs,
            payer_number=profile_obj.phone,
            obj=profile_obj,
        )
        tx.raw_response = {"packs": packs}
        tx.save(update_fields=["raw_response"])
        return redirect("payment_pay", reference=tx.reference)

    return render(
        request,
        "accounts/buy_slots.html",
        {
            "profile": profile_obj,
            "pack_size": conf["SHOP_PACK_SIZE"],
            "pack_price": conf["SHOP_PACK_PRICE"],
            "options": [
                {"packs": n, "slots": conf["SHOP_PACK_SIZE"] * n,
                 "amount": conf["SHOP_PACK_PRICE"] * n}
                for n in (1, 3, 5)
            ],
        },
    )


@login_required
@require_POST
def delete_product(request, product_id):
    """Supprime une annonce et libère son emplacement."""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    if OrderItem.objects.filter(product=product).exists():
        product.is_available = False
        product.save(update_fields=["is_available"])
        messages.info(
            request,
            "Ce produit a déjà été vendu : il est retiré de la vente mais conservé "
            "pour l'historique des commandes.",
        )
    else:
        name = product.name
        product.delete()
        messages.success(request, f"« {name} » supprimé — emplacement libéré.")
    return redirect("seller_dashboard")


@login_required
@require_POST
def toggle_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    product.is_available = not product.is_available
    product.save(update_fields=["is_available"])
    messages.success(request, "Annonce mise en ligne." if product.is_available else "Annonce retirée.")
    return redirect("seller_dashboard")


@login_required
@require_POST
def update_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    price = request.POST.get("base_price", "")
    stock = request.POST.get("stock", "")
    if price.isdigit():
        product.base_price = int(price)
    if stock.isdigit():
        product.stock = int(stock)
        if product.stock > 0:
            product.is_available = True
    product.save()
    messages.success(request, "Produit mis à jour.")
    return redirect("seller_dashboard")


# ---------------------------------------------------------------------
# Livreur
# ---------------------------------------------------------------------
@login_required
def delivery_dashboard(request):
    if not request.user.profile.can_deliver:
        return redirect("become_delivery")

    mine = Order.objects.filter(delivery_driver=request.user)
    profile_obj = request.user.profile

    # Un livreur ne voit que les courses de son pays — et, s'il a indiqué une
    # ville, celles de sa ville en priorité.
    available = Order.objects.filter(
        is_paid=True,
        delivery_driver__isnull=True,
        fulfilment=Order.Fulfilment.DELIVERY,
        status__in=[Order.Status.PAID, Order.Status.PREPARING, Order.Status.READY],
    )
    if profile_obj.country_id:
        available = available.filter(country=profile_obj.country_id)

    return render(
        request,
        "accounts/delivery_dashboard.html",
        {
            "available_orders": available[:20],
            "my_deliveries": mine.exclude(status=Order.Status.DELIVERED)[:20],
            "history": mine.filter(status=Order.Status.DELIVERED)[:10],
            "wallet": get_wallet(request.user),
            "stats": {
                "in_progress": mine.exclude(status=Order.Status.DELIVERED).count(),
                "done": mine.filter(status=Order.Status.DELIVERED).count(),
            },
        },
    )


@login_required
@require_POST
def toggle_delivery_status(request):
    profile_obj = request.user.profile
    profile_obj.is_available = not profile_obj.is_available
    profile_obj.save(update_fields=["is_available"])
    messages.success(
        request, "Vous êtes disponible." if profile_obj.is_available else "Vous êtes hors ligne."
    )
    return redirect("delivery_dashboard")


@login_required
@require_POST
def accept_delivery(request, order_id):
    profile_obj = request.user.profile
    if not profile_obj.can_deliver:
        return redirect("become_delivery")
    if not profile_obj.is_verified:
        messages.warning(
            request,
            "Votre dossier livreur n'est pas encore validé. Complétez-le pour prendre des courses.",
        )
        return redirect("referral_dashboard")

    order = get_object_or_404(Order, id=order_id, delivery_driver__isnull=True, is_paid=True)
    order.delivery_driver = request.user
    order.status = Order.Status.SHIPPED
    order.save(update_fields=["delivery_driver", "status"])

    # On referme la boucle : le client et le vendeur doivent savoir qu'un
    # livreur est en route. Sans ça, la course avançait en silence.
    from notifications.services import notifier

    livreur = profile_obj.display_name
    notifier(
        order.user,
        f"Votre commande {order.order_number} est en route",
        f"{livreur} a pris votre livraison en charge. Gardez votre téléphone à portée.",
        lien=f"/commandes/{order.id}/",
        urgent=True,
    )
    for vendeur in {i.seller for i in order.items.all() if i.seller_id}:
        notifier(
            vendeur,
            f"Un livreur a pris la commande {order.order_number}",
            f"{livreur} vient chercher la commande. Préparez-la s'il reste quelque chose à faire.",
            lien="/commandes/vendeur/",
        )

    messages.success(request, f"Livraison {order.order_number} acceptée.")
    return redirect("delivery_dashboard")


# ---------------------------------------------------------------------
# Administrateur
# ---------------------------------------------------------------------
@staff_member_required
def admin_dashboard(request):
    paid = Order.objects.filter(is_paid=True)
    since = timezone.now() - timedelta(days=30)

    return render(
        request,
        "accounts/admin_dashboard.html",
        {
            "stats": {
                "users": User.objects.count(),
                "sellers": UserProfile.objects.filter(user_type="seller").count(),
                "artisans": Artisan.objects.count(),
                "products": Product.objects.count(),
                "orders": Order.objects.count(),
                "gmv": paid.aggregate(t=Sum("total"))["t"] or 0,
                "revenue": paid.aggregate(t=Sum("commission_total"))["t"] or 0,
                "subs_revenue": Transaction.objects.filter(
                    purpose=Transaction.Purpose.SUBSCRIPTION, status=Transaction.Status.SUCCESS
                ).aggregate(t=Sum("amount"))["t"] or 0,
                "month_gmv": paid.filter(created_at__gte=since).aggregate(t=Sum("total"))["t"] or 0,
            },
            "to_review": Transaction.objects.filter(status=Transaction.Status.AWAITING_REVIEW).count(),
            "confirmations_attente": SellerConfirmation.objects.filter(
                status=SellerConfirmation.Status.PENDING
            ).select_related("order", "seller__profile").order_by("deadline")[:20],
            "boutiques_suspendues": UserProfile.objects.filter(is_store_suspended=True)
            .select_related("user")[:20],
            "payouts_pending": Payout.objects.filter(status=Payout.Status.REQUESTED).count(),
            "recent_orders": Order.objects.select_related("user")[:10],
            "top_products": Product.objects.order_by("-sold_count")[:5],
            "top_sellers": User.objects.annotate(sales=Sum("order_items__subtotal"))
            .filter(sales__gt=0)
            .order_by("-sales")[:5],
            "daily_sales": paid.filter(created_at__gte=since)
            .values("created_at__date")
            .annotate(total=Sum("total"), n=Count("id"))
            .order_by("created_at__date"),
        },
    )
