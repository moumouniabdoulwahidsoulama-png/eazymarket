"""Masquage des numéros de téléphone dans les textes libres.

Un artisan qui veut éviter les 200 FCFA écrira son numéro dans sa
présentation, dans sa fourchette de prix, ou dans le titre d'une
réalisation. Sans ce filtre, le déblocage de contact ne vaut plus rien :
il suffit de lire la page.

Le filtre ne touche pas aux prix : « 25 000 - 100 000 fcfa » reste lisible.
"""

import re

from django import template

register = template.Library()

# Une suite de chiffres, éventuellement séparés par des espaces, points,
# tirets ou barres, précédée ou non d'un indicatif.
SUITE = re.compile(r"(?:\+|00)?\s?\d[\d\s.\-/]{6,20}\d")

# Si l'un de ces mots suit la suite de chiffres, c'est un montant, pas un
# numéro : on n'y touche pas.
MONNAIE = re.compile(r"^\s{0,3}(f\b|fcfa|cfa|francs?|xof|€|\$)", re.IGNORECASE)

REMPLACEMENT = "•• •• •• ••"


def _est_un_numero(texte, suite_apres):
    chiffres = re.sub(r"\D", "", texte)
    # Un numéro africain fait 8 chiffres, 11 avec l'indicatif, 13 avec le +.
    if not 8 <= len(chiffres) <= 13:
        return False
    if MONNAIE.match(suite_apres):
        return False
    return True


@register.filter
def masquer_numeros(valeur, deja_debloque=False):
    """Remplace les numéros de téléphone d'un texte par des points.

    Passer True en argument (le client a payé le déblocage) laisse le
    texte intact.
    """
    if deja_debloque or not valeur:
        return valeur

    texte = str(valeur)
    morceaux = []
    position = 0

    for trouve in SUITE.finditer(texte):
        debut, fin = trouve.span()
        if not _est_un_numero(trouve.group(), texte[fin:fin + 8]):
            continue
        brut = trouve.group()
        # L'espace qui précède appartient à la phrase, pas au numéro.
        prefixe = brut[: len(brut) - len(brut.lstrip())]
        morceaux.append(texte[position:debut])
        morceaux.append(prefixe + REMPLACEMENT)
        position = fin

    morceaux.append(texte[position:])
    return "".join(morceaux)
