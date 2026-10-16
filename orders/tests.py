"""Tests du flux « le vendeur confirme avant d'être payé »."""
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse

from products.models import Product, Category
from orders.models import Order, OrderItem, SellerConfirmation
from orders import services as order_services
from payments.models import WalletEntry
from payments.services import get_wallet

User = get_user_model()


class FluxConfirmation(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Test", slug="test")
        self.vendeur = User.objects.create_user("vendeur", password="x", email="v@x.bf")
        self.vendeur.profile.can_sell  # noqa
        self.vendeur.profile.user_type = "seller"
        # Un vendeur qui existe a payé son pack : sa boutique est ouverte.
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.phone = "70000000"
        self.vendeur.profile.save()
        self.client_u = User.objects.create_user("acheteur", password="x", email="a@x.bf")

        self.p = Product.objects.create(
            name="Frigo", slug="frigo", description="d", base_price=10000, stock=5,
            category=self.cat, seller=self.vendeur, commission_rate=Decimal("5"),
            is_approved=True, is_available=True,
        )

    def _commande(self):
        o = Order.objects.create(user=self.client_u, shipping_name="A", shipping_phone="7",
                                 shipping_address="a", shipping_quartier="q", shipping_city="Ouaga")
        OrderItem.objects.create(order=o, product=self.p, product_name=self.p.name,
                                 product_price=self.p.price, quantity=2,
                                 subtotal=self.p.price * 2, seller=self.vendeur,
                                 commission=Decimal("1000"))
        o.recompute_totals()
        o.is_paid = True
        o.save()
        return o

    def test_ouverture_cree_une_confirmation(self):
        o = self._commande()
        order_services.ouvrir_les_confirmations(o)
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.AWAITING)
        c = o.confirmations.get()
        self.assertEqual(c.seller, self.vendeur)
        self.assertTrue(c.is_pending)
        self.assertGreater(c.hours_left, 20)

    def test_acceptation_credite_le_vendeur(self):
        o = self._commande()
        order_services.ouvrir_les_confirmations(o)
        c = o.confirmations.get()
        order_services.repondre_confirmation(c, accepte=True)
        c.refresh_from_db(); o.refresh_from_db()
        self.assertEqual(c.status, SellerConfirmation.Status.ACCEPTED)
        self.assertEqual(o.status, Order.Status.PREPARING)
        self.assertEqual(self.vendeur.profile.__class__.objects.get(user=self.vendeur).orders_confirmed, 1)
        self.assertGreater(get_wallet(self.vendeur).entries.count(), 0)

    def test_refus_rembourse_le_client(self):
        o = self._commande()
        stock_avant = Product.objects.get(pk=self.p.pk).stock
        order_services.ouvrir_les_confirmations(o)
        self.assertLess(Product.objects.get(pk=self.p.pk).stock, stock_avant)
        c = o.confirmations.get()
        order_services.repondre_confirmation(c, accepte=False, note="rupture")
        c.refresh_from_db(); o.refresh_from_db()
        self.assertEqual(c.status, SellerConfirmation.Status.REFUSED)
        self.assertEqual(o.status, Order.Status.CANCELLED)
        self.assertEqual(Product.objects.get(pk=self.p.pk).stock, stock_avant)
        self.assertGreater(get_wallet(self.client_u).available, 0)
        self.assertGreater(o.refunded_amount, 0)

    def test_expiration_annule_automatiquement(self):
        o = self._commande()
        order_services.ouvrir_les_confirmations(o)
        c = o.confirmations.get()
        c.deadline = timezone.now() - timezone.timedelta(hours=1)
        c.save()
        order_services.traiter_les_commandes_expirees()
        c.refresh_from_db(); o.refresh_from_db()
        self.assertEqual(c.status, SellerConfirmation.Status.EXPIRED)
        self.assertEqual(o.status, Order.Status.CANCELLED)
        self.assertGreater(get_wallet(self.client_u).available, 0)

    def test_suspension_apres_trop_d_annulations(self):
        for _ in range(5):
            o = self._commande()
            order_services.ouvrir_les_confirmations(o)
            order_services.repondre_confirmation(o.confirmations.get(), accepte=False)
        self.vendeur.profile.refresh_from_db()
        self.assertTrue(self.vendeur.profile.is_store_suspended)
        self.assertFalse(self.vendeur.profile.can_sell)
        self.assertNotIn(self.p, Product.objects.visible())

    def test_pages_vendeur_et_client(self):
        o = self._commande()
        order_services.ouvrir_les_confirmations(o)
        self.client.login(username="vendeur", password="x")
        r = self.client.get(reverse("seller_orders"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "J'ai le produit")
        r = self.client.get(reverse("seller_dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "attend")

        self.client.login(username="acheteur", password="x")
        r = self.client.get(reverse("order_detail", args=[o.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Votre paiement est protégé")
        self.assertNotContains(r, "70000000")  # numéro du vendeur jamais affiché

    def test_reponse_via_la_vue(self):
        o = self._commande()
        order_services.ouvrir_les_confirmations(o)
        c = o.confirmations.get()
        self.client.login(username="vendeur", password="x")
        r = self.client.post(reverse("respond_confirmation", args=[c.id]), {"reponse": "oui"})
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.status, SellerConfirmation.Status.ACCEPTED)

    def test_messagerie(self):
        o = self._commande()
        self.client.login(username="acheteur", password="x")
        r = self.client.post(reverse("post_order_message", args=[o.id]), {"body": "Bonjour"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(o.messages.count(), 1)
        r = self.client.get(reverse("order_detail", args=[o.id]))
        self.assertContains(r, "Bonjour")


class PagesQuiSAffichent(TestCase):
    """Les pages touchées par le flux de confirmation doivent rendre sans erreur."""

    def setUp(self):
        self.cat = Category.objects.create(name="Test", slug="test")
        self.vendeur = User.objects.create_user("v2", password="x")
        self.vendeur.profile.user_type = "seller"
        # Un vendeur qui existe a payé son pack : sa boutique est ouverte.
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.store_name = "Boutique Test"
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.save()
        self.p = Product.objects.create(
            name="Sac", slug="sac", description="d", base_price=5000, stock=0,
            made_to_order=True, lead_time_days=3, category=self.cat, seller=self.vendeur,
            commission_rate=Decimal("5"), is_approved=True, is_available=True,
        )
        self.acheteur = User.objects.create_user("a2", password="x")

    def test_fiche_produit_sur_commande(self):
        r = self.client.get(self.p.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Sur commande")
        self.assertContains(r, "Achat protégé")
        self.assertContains(r, "Nouveau vendeur")

    def test_vitrine_boutique(self):
        self.vendeur.profile.refresh_from_db()
        r = self.client.get(reverse("store_front", args=[self.vendeur.profile.store_slug]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nouveau vendeur")

    def test_checkout(self):
        from cart.models import Cart, CartItem
        self.client.login(username="a2", password="x")
        cart, _ = Cart.objects.get_or_create(user=self.acheteur)
        CartItem.objects.create(cart=cart, product=self.p, quantity=1)
        r = self.client.get(reverse("checkout"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Votre paiement est protégé")
        self.assertContains(r, "sous 24 h sans réponse")

    def test_produit_sur_commande_reste_visible(self):
        self.assertIn(self.p, Product.objects.visible())


class TableauDeBordAdmin(TestCase):
    def test_relance_whatsapp_et_page_admin(self):
        cat = Category.objects.create(name="C", slug="c")
        v = User.objects.create_user("v3", password="x")
        v.profile.user_type = "seller"
        v.profile.is_store_active = True
        v.profile.extra_slots = 10
        v.profile.phone = "64691208"
        v.profile.save()
        a = User.objects.create_user("a3", password="x")
        p = Product.objects.create(name="Chaise", slug="chaise", description="d",
                                   base_price=3000, stock=2, category=cat, seller=v,
                                   commission_rate=Decimal("5"), is_approved=True)
        o = Order.objects.create(user=a, shipping_name="A", shipping_phone="7",
                                 shipping_address="a", shipping_quartier="q", shipping_city="Ouaga")
        OrderItem.objects.create(order=o, product=p, product_name=p.name, product_price=p.price,
                                 quantity=1, subtotal=p.price, seller=v, commission=Decimal("200"))
        o.recompute_totals(); o.is_paid = True; o.save()
        order_services.ouvrir_les_confirmations(o)
        c = o.confirmations.get()
        self.assertIn("wa.me/22664691208", c.relance_whatsapp)

        admin = User.objects.create_superuser("boss", "b@x.bf", "x")
        self.client.force_login(admin)
        r = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "en attente de confirmation")
        self.assertContains(r, "wa.me/22664691208")


class ArgentLibereALaLivraison(TestCase):
    """Le vendeur n'est payé que lorsque le client a reçu."""

    def setUp(self):
        self.cat = Category.objects.create(name="T", slug="t")
        self.vendeur = User.objects.create_user("v9", password="x")
        self.vendeur.profile.user_type = "seller"
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.save()
        self.acheteur = User.objects.create_user("a9", password="x")
        self.p = Product.objects.create(
            name="Ventilateur", slug="ventilateur", description="d", base_price=8000,
            stock=3, category=self.cat, seller=self.vendeur,
            commission_rate=Decimal("5"), is_approved=True,
        )

    def _commande_confirmee(self):
        o = Order.objects.create(user=self.acheteur, shipping_name="A", shipping_phone="70000000",
                                 shipping_address="a", shipping_quartier="q", shipping_city="Ouaga")
        OrderItem.objects.create(order=o, product=self.p, product_name=self.p.name,
                                 product_price=self.p.price, quantity=1, subtotal=self.p.price,
                                 seller=self.vendeur, commission=Decimal("400"))
        o.recompute_totals(); o.is_paid = True; o.save()
        order_services.ouvrir_les_confirmations(o)
        order_services.repondre_confirmation(o.confirmations.get(), accepte=True)
        return o

    def test_confirmer_ne_suffit_plus_a_etre_paye(self):
        o = self._commande_confirmee()
        ligne = get_wallet(self.vendeur).entries.get(kind="sale")
        self.assertFalse(ligne.is_released)
        self.assertIsNone(ligne.release_at)
        # Même dans trois mois, la tâche ne libère rien sans livraison.
        from payments.services import release_due_entries
        self.assertEqual(release_due_entries(), 0)
        self.assertEqual(get_wallet(self.vendeur).available, 0)

    def test_la_livraison_demarre_le_compte_a_rebours(self):
        o = self._commande_confirmee()
        order_services.marquer_livree(o)
        ligne = get_wallet(self.vendeur).entries.get(kind="sale")
        self.assertIsNotNone(ligne.release_at)
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.DELIVERED)
        self.assertTrue(o.fenetre_contestation_ouverte)

        ligne.release_at = timezone.now() - timezone.timedelta(minutes=1)
        ligne.save()
        from payments.services import release_due_entries
        self.assertEqual(release_due_entries(), 1)
        self.assertGreater(get_wallet(self.vendeur).available, 0)

    def test_non_reception_rebloque_l_argent(self):
        o = self._commande_confirmee()
        order_services.marquer_livree(o)
        order_services.signaler_non_recu(o, note="rien reçu")
        ligne = get_wallet(self.vendeur).entries.get(kind="sale")
        self.assertIsNone(ligne.release_at)
        self.assertFalse(ligne.is_released)
        o.refresh_from_db()
        self.assertTrue(o.non_recu_signale)
        self.assertFalse(o.fenetre_contestation_ouverte)

    def test_le_client_signale_depuis_la_page(self):
        o = self._commande_confirmee()
        order_services.marquer_livree(o)
        self.client.login(username="a9", password="x")
        r = self.client.get(reverse("order_detail", args=[o.id]))
        self.assertContains(r, "Je n'ai pas reçu ma commande")
        r = self.client.post(reverse("signaler_non_recu", args=[o.id]), {"note": "jamais arrivé"})
        self.assertEqual(r.status_code, 302)
        o.refresh_from_db()
        self.assertTrue(o.non_recu_signale)

    def test_commandes_jamais_livrees_remontent(self):
        o = self._commande_confirmee()
        c = o.confirmations.get()
        c.responded_at = timezone.now() - timezone.timedelta(days=30)
        c.save()
        self.assertIn(o, order_services.commandes_sans_livraison())
        order_services.marquer_livree(o)
        self.assertNotIn(o, order_services.commandes_sans_livraison())


class RemboursementEnArgent(TestCase):
    """Le client choisit : garder l'avoir, ou récupérer son argent."""

    def setUp(self):
        self.acheteur = User.objects.create_user("client9", password="x")
        self.order = Order.objects.create(
            user=self.acheteur, shipping_name="A", shipping_phone="70112233",
            shipping_address="a", shipping_quartier="q", shipping_city="Ouaga",
        )
        order_services._rembourser(self.order, Decimal("6000"), motif="test")

    def test_l_avoir_est_immediatement_utilisable(self):
        self.assertEqual(get_wallet(self.acheteur).available, 6000)

    def test_demander_l_argent_reserve_la_somme(self):
        from payments.services import demander_remboursement
        payout, message = demander_remboursement(
            self.acheteur, numero="70112233", canal="orange", order=self.order
        )
        self.assertIsNotNone(payout)
        self.assertEqual(payout.kind, "refund")
        self.assertEqual(payout.amount, 6000)
        # La somme est réservée : impossible de la dépenser en attendant.
        self.assertEqual(get_wallet(self.acheteur).available, 0)

    def test_le_versement_debite_le_compte(self):
        from payments.services import demander_remboursement
        payout, _ = demander_remboursement(self.acheteur, numero="70112233", canal="orange")
        payout.mark_paid()
        w = get_wallet(self.acheteur)
        self.assertEqual(w.available, 0)
        self.assertEqual(w.locked, 0)
        self.assertEqual(w._sum(), 0)

    def test_petit_montant_refuse(self):
        from payments.services import demander_remboursement
        o2 = Order.objects.create(user=User.objects.create_user("petit", password="x"),
                                  shipping_name="B", shipping_phone="7", shipping_address="b",
                                  shipping_quartier="q", shipping_city="Ouaga")
        order_services._rembourser(o2, Decimal("200"), motif="test")
        payout, message = demander_remboursement(o2.user, numero="70000000")
        self.assertIsNone(payout)
        self.assertIn("500", message)

    def test_pas_deux_demandes_en_meme_temps(self):
        from payments.services import demander_remboursement
        demander_remboursement(self.acheteur, numero="70112233", canal="orange")
        payout, message = demander_remboursement(self.acheteur, numero="70112233", canal="orange")
        self.assertIsNone(payout)
        self.assertIn("déjà en cours", message)

    def test_depuis_la_page_commande(self):
        self.client.login(username="client9", password="x")
        r = self.client.get(reverse("order_detail", args=[self.order.id]))
        self.assertContains(r, "recevoir l'argent sur mon mobile money")
        r = self.client.post(reverse("demander_mon_remboursement", args=[self.order.id]),
                             {"numero": "70112233", "canal": "orange"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(get_wallet(self.acheteur).available, 0)


class QuiPeutDeclarerLaLivraison(TestCase):
    """Sans ce bouton, le vendeur ne serait jamais payé."""

    def setUp(self):
        self.cat = Category.objects.create(name="Papeterie", slug="papeterie")
        self.vendeur = User.objects.create_user("v10", password="x")
        self.vendeur.profile.user_type = "seller"
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.save()
        self.acheteur = User.objects.create_user("a10", password="x")
        self.p = Product.objects.create(
            name="Bic", slug="bic", description="d", base_price=200, stock=50,
            category=self.cat, seller=self.vendeur, commission_rate=Decimal("5"),
            is_approved=True,
        )
        self.order = self._commande()

    def _commande(self):
        o = Order.objects.create(user=self.acheteur, shipping_name="F", shipping_phone="70000000",
                                 shipping_address="a", shipping_quartier="q", shipping_city="Ouaga")
        OrderItem.objects.create(order=o, product=self.p, product_name=self.p.name,
                                 product_price=self.p.price, quantity=1, subtotal=self.p.price,
                                 seller=self.vendeur, commission=Decimal("100"))
        o.recompute_totals(); o.is_paid = True; o.save()
        order_services.ouvrir_les_confirmations(o)
        order_services.repondre_confirmation(o.confirmations.get(), accepte=True)
        return o

    def test_le_vendeur_voit_le_bouton_de_remise(self):
        self.client.login(username="v10", password="x")
        r = self.client.get(reverse("seller_orders"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Oui, remis au client")

    def test_le_vendeur_declare_la_remise(self):
        self.client.login(username="v10", password="x")
        r = self.client.post(reverse("update_order_status", args=[self.order.id]),
                             {"status": "delivered"})
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertIsNotNone(self.order.delivered_at)
        ligne = get_wallet(self.vendeur).entries.get(kind="sale")
        self.assertIsNotNone(ligne.release_at)
        # Le client garde son droit de contester.
        self.assertTrue(self.order.fenetre_contestation_ouverte)

    def test_le_client_confirme_lui_meme(self):
        self.client.login(username="a10", password="x")
        r = self.client.get(reverse("order_detail", args=[self.order.id]))
        self.assertContains(r, "j'ai reçu ma commande")
        r = self.client.post(reverse("confirmer_reception", args=[self.order.id]))
        self.assertEqual(r.status_code, 302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.reception_confirmee)
        self.assertIsNotNone(self.order.delivered_at)
        ligne = get_wallet(self.vendeur).entries.get(kind="sale")
        self.assertIsNotNone(ligne.release_at)
        # Rien à contester quand on vient de dire qu'on a reçu.
        self.assertFalse(self.order.fenetre_contestation_ouverte)

    def test_un_inconnu_ne_peut_pas_confirmer(self):
        User.objects.create_user("curieux", password="x")
        self.client.login(username="curieux", password="x")
        r = self.client.post(reverse("confirmer_reception", args=[self.order.id]))
        self.assertEqual(r.status_code, 404)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.delivered_at)

    def test_pas_de_double_declaration(self):
        order_services.marquer_livree(self.order)
        premiere = Order.objects.get(pk=self.order.pk).delivered_at
        self.client.login(username="a10", password="x")
        self.client.post(reverse("confirmer_reception", args=[self.order.id]))
        self.assertEqual(Order.objects.get(pk=self.order.pk).delivered_at, premiere)


class PaiementLivreur(TestCase):
    """Le livreur doit toucher les frais de livraison, à la remise."""

    def setUp(self):
        self.cat = Category.objects.create(name="D", slug="d")
        self.vendeur = User.objects.create_user("vend_liv", password="x")
        self.vendeur.profile.user_type = "seller"
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.save()
        self.livreur = User.objects.create_user("le_livreur", password="x")
        lp = self.livreur.profile
        lp.user_type = "delivery"; lp.is_driver = True; lp.save()
        self.acheteur = User.objects.create_user("client_liv", password="x")
        self.p = Product.objects.create(
            name="Sac riz", slug="sac-riz", description="d", base_price=15000, stock=10,
            category=self.cat, seller=self.vendeur, commission_rate=Decimal("5"), is_approved=True,
        )

    def _commande_livree(self):
        o = Order.objects.create(
            user=self.acheteur, shipping_name="A", shipping_phone="70", shipping_address="a",
            shipping_quartier="q", shipping_city="Ouaga",
            fulfilment=Order.Fulfilment.DELIVERY, delivery_fee=Decimal("1000"),
            delivery_driver=self.livreur,
        )
        OrderItem.objects.create(order=o, product=self.p, product_name=self.p.name,
                                 product_price=self.p.price, quantity=1, subtotal=self.p.price,
                                 seller=self.vendeur, commission=Decimal("750"))
        o.recompute_totals(); o.is_paid = True; o.save()
        order_services.ouvrir_les_confirmations(o)
        order_services.repondre_confirmation(o.confirmations.get(), accepte=True)
        return o

    def test_le_livreur_est_credite_a_la_remise(self):
        o = self._commande_livree()
        # Avant la remise : rien pour le livreur.
        self.assertEqual(get_wallet(self.livreur).entries.filter(kind="delivery").count(), 0)
        order_services.marquer_livree(o, par=self.livreur)
        ligne = get_wallet(self.livreur).entries.get(kind="delivery")
        self.assertEqual(ligne.amount, Decimal("1000"))
        self.assertIsNotNone(ligne.release_at)

    def test_pas_de_double_credit(self):
        o = self._commande_livree()
        order_services.marquer_livree(o, par=self.livreur)
        order_services.marquer_livree(o, par=self.livreur)
        self.assertEqual(get_wallet(self.livreur).entries.filter(kind="delivery").count(), 1)

    def test_litige_rebloque_les_frais_du_livreur(self):
        o = self._commande_livree()
        order_services.marquer_livree(o, par=self.livreur)
        order_services.signaler_non_recu(o, note="rien reçu")
        ligne = get_wallet(self.livreur).entries.get(kind="delivery")
        self.assertIsNone(ligne.release_at)

    def test_retrait_pickup_ne_paie_personne_pour_la_livraison(self):
        o = Order.objects.create(
            user=self.acheteur, shipping_name="A", shipping_phone="70", shipping_address="a",
            shipping_quartier="q", shipping_city="Ouaga",
            fulfilment=Order.Fulfilment.PICKUP, delivery_fee=Decimal("0"),
        )
        OrderItem.objects.create(order=o, product=self.p, product_name=self.p.name,
                                 product_price=self.p.price, quantity=1, subtotal=self.p.price,
                                 seller=self.vendeur, commission=Decimal("750"))
        o.recompute_totals(); o.is_paid = True; o.save()
        order_services.ouvrir_les_confirmations(o)
        order_services.repondre_confirmation(o.confirmations.get(), accepte=True)
        order_services.marquer_livree(o)
        self.assertEqual(WalletEntry.objects.filter(order=o, kind="delivery").count(), 0)
