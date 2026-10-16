"""Panier."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Product

from .models import Cart, CartItem


def _get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def cart_view(request):
    cart = _get_cart(request.user)
    return render(
        request,
        "cart/cart.html",
        {"cart": cart, "issues": cart.has_stock_issue(), "delivery_fee": cart.delivery_fee()},
    )


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not product.in_stock:
        messages.error(request, f"« {product.name} » n'est plus disponible.")
        return redirect(request.META.get("HTTP_REFERER", "home"))

    quantity = max(1, int(request.POST.get("quantity", 1) or 1))
    cart = _get_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": min(quantity, product.max_quantity)}
    )
    if not created:
        item.quantity = min(item.quantity + quantity, product.max_quantity)
        item.save(update_fields=["quantity"])

    messages.success(request, f"« {product.name} » ajouté au panier.")
    if request.POST.get("next") == "cart":
        return redirect("cart")
    return redirect(request.META.get("HTTP_REFERER", product.get_absolute_url()))


@login_required
@require_POST
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    name = item.product.name
    item.delete()
    messages.info(request, f"« {name} » retiré du panier.")
    return redirect("cart")


@login_required
@require_POST
def update_cart_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get("quantity", 1) or 0)
    if quantity <= 0:
        item.delete()
        messages.info(request, "Article retiré du panier.")
    else:
        item.quantity = min(quantity, item.product.max_quantity or 1)
        item.save(update_fields=["quantity"])
        messages.success(request, "Panier mis à jour.")
    return redirect("cart")


@login_required
@require_POST
def clear_cart(request):
    _get_cart(request.user).items.all().delete()
    messages.info(request, "Panier vidé.")
    return redirect("cart")


@login_required
def cart_count(request):
    return JsonResponse({"count": _get_cart(request.user).total_items})
