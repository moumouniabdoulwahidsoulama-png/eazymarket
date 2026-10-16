"""Catalogue : accueil, recherche, fiche produit, favoris, avis."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.models import OrderItem
from regions.utils import current_country
from services.models import Artisan, ServiceCategory

from .models import Category, Favorite, Product, ProductReview

PER_PAGE = 24


def home(request):
    """Accueil : la double entrée boutique / services, dans le pays affiché."""
    country = current_country(request)
    base = Product.objects.visible().in_country(country).select_related("category", "seller")

    context = {
        "featured": base.filter(is_featured=True)[:8],
        "new_products": base.order_by("-created_at")[:8],
        "best_sellers": base.order_by("-sold_count")[:8],
        "categories": Category.objects.filter(parent__isnull=True)[:12],
        "service_categories": ServiceCategory.objects.all()[:8],
        "top_artisans": Artisan.objects.visible()
        .in_country(country)
        .select_related("service_category")
        .order_by("-is_featured", "-rating")[:4],
        "stats": {
            "products": base.count(),
            "artisans": Artisan.objects.visible().in_country(country).count(),
            "sellers": base.values("seller").distinct().count(),
        },
    }
    return render(request, "products/home.html", context)


def _filtered(request, queryset):
    """Filtres et tri communs au catalogue et à la recherche."""
    price_min = request.GET.get("min")
    price_max = request.GET.get("max")
    condition = request.GET.get("etat")
    sort = request.GET.get("tri", "recent")

    if price_min and price_min.isdigit():
        queryset = queryset.filter(base_price__gte=int(price_min))
    if price_max and price_max.isdigit():
        queryset = queryset.filter(base_price__lte=int(price_max))
    if condition in dict(Product.Condition.choices):
        queryset = queryset.filter(condition=condition)

    order = {
        "recent": "-created_at",
        "prix_asc": "base_price",
        "prix_desc": "-base_price",
        "populaire": "-sold_count",
        "note": "-rating",
    }.get(sort, "-created_at")
    return queryset.order_by(order), sort


def _paginate(request, queryset):
    return Paginator(queryset, PER_PAGE).get_page(request.GET.get("page"))


def product_list(request):
    products = (
        Product.objects.visible()
        .in_country(current_country(request))
        .select_related("category", "seller")
    )
    products, sort = _filtered(request, products)
    return render(
        request,
        "products/product_list.html",
        {
            "page_obj": _paginate(request, products),
            "categories": Category.objects.all(),
            "sort": sort,
            "title": "Tous les produits",
        },
    )


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = (
        Product.objects.visible()
        .in_country(current_country(request))
        .filter(Q(category=category) | Q(category__parent=category))
        .select_related("category", "seller")
    )
    products, sort = _filtered(request, products)
    return render(
        request,
        "products/product_list.html",
        {
            "page_obj": _paginate(request, products),
            "category": category,
            "categories": Category.objects.all(),
            "sort": sort,
            "title": category.name,
        },
    )


def search(request):
    country = current_country(request)
    query = request.GET.get("q", "").strip()
    products = Product.objects.visible().in_country(country).select_related("category", "seller")
    artisans = Artisan.objects.none()

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(category__name__icontains=query)
        )
        artisans = (
            Artisan.objects.visible()
            .in_country(country)
            .filter(
                Q(full_name__icontains=query)
                | Q(description__icontains=query)
                | Q(service_category__name__icontains=query)
                | Q(quartier__icontains=query)
            )
            .select_related("service_category")[:6]
        )

    products, sort = _filtered(request, products)
    return render(
        request,
        "products/search.html",
        {
            "query": query,
            "page_obj": _paginate(request, products),
            "artisans": artisans,
            "categories": Category.objects.all(),
            "sort": sort,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category", "seller__profile"), slug=slug
    )
    if not product.is_approved and not request.user.is_staff and product.seller != request.user:
        messages.warning(request, "Cette annonce n'est pas disponible.")
        return redirect("home")

    Product.objects.filter(pk=product.pk).update(views_count=product.views_count + 1)

    can_review = False
    if request.user.is_authenticated:
        can_review = (
            OrderItem.objects.filter(
                product=product, order__user=request.user, order__is_paid=True
            ).exists()
            and not ProductReview.objects.filter(product=product, user=request.user).exists()
        )

    related = (
        Product.objects.visible()
        .in_country(product.country)
        .filter(category=product.category)
        .exclude(pk=product.pk)[:4]
    )

    from videos.models import Video

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "videos": Video.pour(product),
            "gallery": product.gallery.all(),
            "reviews": product.reviews.select_related("user")[:10],
            "related": related,
            "can_review": can_review,
            "is_favorite": request.user.is_authenticated
            and Favorite.objects.filter(user=request.user, product=product).exists(),
        },
    )


def store_front(request, slug):
    """Vitrine publique d'un vendeur."""
    from accounts.models import UserProfile

    profile = get_object_or_404(
        UserProfile, store_slug=slug, is_store_active=True, is_store_suspended=False
    )
    products = Product.objects.visible().filter(seller=profile.user)
    products, sort = _filtered(request, products)
    return render(
        request,
        "products/store_front.html",
        {"store": profile, "page_obj": _paginate(request, products), "sort": sort},
    )


@login_required
@require_POST
def add_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    bought = OrderItem.objects.filter(
        product=product, order__user=request.user, order__is_paid=True
    ).exists()
    if not bought:
        messages.error(request, "Seuls les acheteurs de ce produit peuvent laisser un avis.")
        return redirect(product.get_absolute_url())

    rating = int(request.POST.get("rating", 0) or 0)
    comment = request.POST.get("comment", "").strip()
    if not (1 <= rating <= 5) or len(comment) < 5:
        messages.error(request, "Choisissez une note et écrivez quelques mots.")
        return redirect(product.get_absolute_url())

    ProductReview.objects.update_or_create(
        product=product, user=request.user, defaults={"rating": rating, "comment": comment}
    )
    messages.success(request, "Merci pour votre avis !")
    return redirect(product.get_absolute_url())


@login_required
def toggle_favorite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    favorite = Favorite.objects.filter(user=request.user, product=product).first()
    if favorite:
        favorite.delete()
        active = False
    else:
        Favorite.objects.create(user=request.user, product=product)
        active = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorite": active})
    return redirect(request.META.get("HTTP_REFERER", product.get_absolute_url()))


@login_required
def favorites(request):
    items = Favorite.objects.filter(user=request.user).select_related("product__category")
    return render(request, "products/favorites.html", {"favorites": items})
