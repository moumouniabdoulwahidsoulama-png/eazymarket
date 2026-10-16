"""Variables disponibles dans tous les templates."""

from django.conf import settings


def site_context(request):
    conf = settings.EAZYMARKET

    country = None
    countries = []
    try:
        from regions.models import Country
        from regions.utils import current_country

        country = current_country(request)
        countries = list(Country.objects.filter(is_active=True))
    except Exception:  # base pas encore migrée
        pass

    pricing = country.pricing if country is not None else {
        "CURRENCY": conf["CURRENCY"],
        "SHOP_PACK_PRICE": conf["SHOP_PACK_PRICE"],
        "SHOP_PACK_SIZE": conf["SHOP_PACK_SIZE"],
        "SHOP_FREE_SLOTS": conf["SHOP_FREE_SLOTS"],
        "ARTISAN_SUB_PRICE": conf["ARTISAN_SUB_PRICE"],
        "ARTISAN_SUB_DAYS": conf["ARTISAN_SUB_DAYS"],
        "CONTACT_UNLOCK_PRICE": conf["CONTACT_UNLOCK_PRICE"],
        "CONTACT_UNLOCK_DAYS": conf["CONTACT_UNLOCK_DAYS"],
        "DELIVERY_FEE_CITY": conf["DELIVERY_FEE_CITY"],
        "DELIVERY_FEE_OUT": conf["DELIVERY_FEE_OUT"],
        "FREE_DELIVERY_FROM": conf["FREE_DELIVERY_FROM"],
        "PAYOUT_MIN": conf["PAYOUT_MIN"],
        "COMMISSION_RATE": conf["COMMISSION_RATE"],
        "COMMISSION_MIN": conf["COMMISSION_MIN"],
        "DELIVERY_REQUIRED_SHARES": conf["DELIVERY_REQUIRED_SHARES"],
    }

    ctx = {
        "SITE": conf,
        "PRICING": pricing,
        # Réglages vidéo, utilisés par les formulaires d'envoi
        "VIDEO": {
            "MAX_SECONDS": conf["VIDEO_MAX_SECONDS"],
            "MAX_MB": conf["VIDEO_MAX_MB"],
            "FREE_SLOTS": conf["VIDEO_FREE_SLOTS"],
            "PACK_SIZE": conf["VIDEO_PACK_SIZE"],
            "PACK_PRICE": conf["VIDEO_PACK_PRICE"],
        },
        "CURRENCY": pricing["CURRENCY"],
        "COUNTRY": country,
        "COUNTRIES": countries,
        "CITY": country.main_city if country is not None else conf["CITY"],
        "SUPPORT_PHONE": (country.support_phone if country and country.support_phone
                          else conf["SUPPORT_PHONE"]),
        "SUPPORT_WHATSAPP": (country.support_whatsapp if country and country.support_whatsapp
                             else conf["WHATSAPP"]),
        "unread_notifications": 0,
        "cart_count": 0,
        "is_artisan": False,
    }

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        try:
            ctx["unread_notifications"] = user.notifications.filter(is_read=False).count()
        except Exception:
            pass
        try:
            cart = getattr(user, "cart", None)
            if cart is not None:
                ctx["cart_count"] = cart.total_items
        except Exception:
            pass
        ctx["is_artisan"] = hasattr(user, "artisan_profile")
    return ctx
