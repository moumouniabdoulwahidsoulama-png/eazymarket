"""Contrat commun à tous les fournisseurs SMS."""

import re
from dataclasses import dataclass


@dataclass
class SmsResult:
    ok: bool
    reference: str = ""
    message: str = ""


class SmsProvider:
    name = "base"
    label = "Fournisseur SMS"

    def send(self, numero, texte):
        raise NotImplementedError

    # ------------------------------------------------------------------
    @staticmethod
    def normaliser(numero, indicatif="226"):
        """Met un numéro au format international, sans espaces ni signe +.

        « +226 64 69 12 08 », « 64691208 » et « 00226 64691208 » donnent
        tous « 22664691208 ».
        """
        chiffres = re.sub(r"\D", "", str(numero or ""))
        if not chiffres:
            return ""
        if chiffres.startswith("00"):
            chiffres = chiffres[2:]
        if not chiffres.startswith(indicatif) and len(chiffres) <= 10:
            chiffres = indicatif + chiffres
        return chiffres

    @staticmethod
    def raccourcir(texte, limite=300):
        """Un SMS long coûte plusieurs messages : on reste concis."""
        texte = " ".join(str(texte or "").split())
        return texte if len(texte) <= limite else texte[: limite - 1] + "…"
