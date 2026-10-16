"""Tests des alertes d'encaissement."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification
from payments.models import Transaction
from payments.services import start_transaction

User = get_user_model()


class AlerteQuandUnClientDeclareSonPaiement(TestCase):
    """Un paiement déclaré doit réveiller l'administrateur, pas l'attendre."""

    def setUp(self):
        self.patron = User.objects.create_superuser(
            "patron", "patron@exemple.bf", "x")
        self.client_u = User.objects.create_user("acheteur", password="x")
        self.tx = start_transaction(
            user=self.client_u, purpose=Transaction.Purpose.ORDER,
            amount=1500, payer_number="70123456",
        )
        self.client.login(username="acheteur", password="x")

    def test_l_administrateur_est_prevenu(self):
        reponse = self.client.post(
            reverse("payment_declare", args=[self.tx.reference]),
            {"operator_id": "PP250914.1432.A12345", "payer_number": "70123456"},
        )
        self.assertEqual(reponse.status_code, 302)

        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.Status.AWAITING_REVIEW)

        alertes = Notification.objects.filter(user=self.patron)
        self.assertEqual(alertes.count(), 1)
        alerte = alertes.first()
        self.assertIn("1 500", alerte.title)
        self.assertIn("PP250914.1432.A12345", alerte.message)
        self.assertTrue(alerte.is_urgent)

    def test_un_e_mail_part_aussi(self):
        self.client.post(
            reverse("payment_declare", args=[self.tx.reference]),
            {"operator_id": "PP250914.1432.A12345"},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("patron@exemple.bf", mail.outbox[0].recipients())
        self.assertIn("valider", mail.outbox[0].subject.lower())

    def test_le_client_n_est_pas_alerte_a_la_place(self):
        self.client.post(
            reverse("payment_declare", args=[self.tx.reference]),
            {"operator_id": "PP250914.1432.A12345"},
        )
        self.assertEqual(Notification.objects.filter(user=self.client_u).count(), 0)
