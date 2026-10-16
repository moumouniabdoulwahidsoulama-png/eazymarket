from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render


def about(request):
    return render(request, "pages/about.html")


def faq(request):
    return render(request, "pages/faq.html")


def terms(request):
    return render(request, "pages/terms.html")


def how_it_works(request):
    return render(request, "pages/how_it_works.html")


def sell(request):
    """Page d'atterrissage : convaincre vendeurs, artisans et livreurs de s'inscrire."""
    return render(request, "pages/sell.html")


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("message", "").strip()

        if not all([name, email, body]):
            messages.error(request, "Merci de remplir votre nom, votre e-mail et votre message.")
            return redirect("contact")

        try:
            send_mail(
                f"[EazyMarket] {subject or 'Message du site'}",
                f"De : {name} <{email}>\n\n{body}",
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            messages.success(request, "Message envoyé. Nous répondons sous 24 h.")
        except Exception:
            messages.error(
                request, "L'envoi a échoué. Écrivez-nous directement à " + settings.CONTACT_EMAIL
            )
        return redirect("contact")

    return render(request, "pages/contact.html")
