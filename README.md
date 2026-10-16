# EazyMarket

Place de marché burkinabè à double entrée : **une boutique** (produits vendus par
des commerçants) et **un annuaire de professionnels** (artisans qui répondent par
devis). Paiement par mobile money, portefeuille vendeur, reversements suivis.

---

## Démarrage rapide

### Windows
Double-cliquez sur `run_server.bat`. Le script crée l'environnement virtuel,
installe les dépendances, prépare le `.env`, applique les migrations et lance le
serveur.

### Ligne de commande

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
copy .env.example .env         # cp sous Linux/macOS — puis remplissez-le

python manage.py migrate
python manage.py init_catalogue        # 12 pays, 22 rayons, 65 métiers (données réelles)
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Le site est sur <http://127.0.0.1:8000>. Depuis un téléphone sur le même Wi-Fi,
utilisez l'adresse IP de l'ordinateur (le serveur écoute sur `0.0.0.0`).

`init_catalogue` n'installe **aucune donnée fictive** : les pays, les villes,
les rayons de la boutique et les métiers de l'annuaire, prêts à recevoir de
vrais vendeurs et de vrais artisans. La commande est idempotente.

**Administration :** <http://127.0.0.1:8000/django-admin/> (`/admin/` y renvoie).
En cas de souci de connexion : `python manage.py admin_reset`.

---

## Organisation du projet

```
boutique/
├── EazyMarket/           Configuration : settings, urls, context_processors
├── regions/              Pays, villes, comptes d'encaissement (multi-pays)
├── accounts/             Profils, rôles, tableaux de bord vendeur/livreur/admin
├── products/             Catalogue, catégories, avis produits, favoris
├── cart/                 Panier
├── orders/               Commandes, suivi, espaces vendeur et livreur
├── services/             Artisans, demandes, DEVIS, messagerie, avis
├── payments/             Transactions, portefeuilles, retraits
│   └── providers/        manual.py · cinetpay.py · base.py (interface)
├── delivery/             Parrainage livreurs
├── notifications/        Notifications internes
├── pages/                Pages éditoriales + commande seed_demo
├── templates/            TOUS les gabarits (base, partials/, un dossier par app)
├── static/
│   ├── css/              tokens.css · base.css · components.css · pages.css · icons.css
│   ├── js/app.js
│   └── img/              logo.svg · logo-mark.svg · favicon.svg
├── media/                Fichiers envoyés par les utilisateurs
└── _legacy/              Ancienne version des gabarits et migrations (à supprimer quand tout est validé)
```

**Règle de style :** tout le design passe par `static/css/tokens.css`.
Changer la couleur de marque = changer `--brand-500` à un seul endroit.

**Aucune dépendance réseau pour l'affichage :** les icônes sont servies depuis
`static/css/icons.css` (Font Awesome Free en SVG intégré). Le site s'affiche
correctement même avec une connexion très lente ou coupée.

---

## Configuration

Tout ce qui dépend de l'environnement est dans `.env` (jamais dans le code).
Voir `.env.example` pour la liste complète. Les valeurs clés :

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | À changer impérativement avant la mise en ligne |
| `DJANGO_DEBUG` | `False` en production |
| `SHOP_FREE_SLOTS` | Annonces offertes à un nouveau vendeur (défaut : 2) |
| `SHOP_PACK_SIZE` / `SHOP_PACK_PRICE` | Pack d'annonces (défaut : 10 pour 5 000 F) |
| `COMMISSION_RATE` / `COMMISSION_MIN` | Commission (défaut : 5 %, plancher 100 F) |
| `ARTISAN_SUB_PRICE` / `ARTISAN_SUB_DAYS` | Abonnement artisan (défaut : 1 000 F / 60 j) |
| `ARTISAN_FREE_LAUNCH` | `True` = annuaire visible sans payer (opération de lancement) |
| `CONTACT_UNLOCK_PRICE` | Prix du déblocage d'un numéro d'artisan (défaut : 200 F) |
| `DELIVERY_REQUIRED_SHARES` | Personnes à parrainer pour activer un livreur (défaut : 3) |
| `PAYMENT_PROVIDER` | `manual` ou `cinetpay` |
| `ORANGE_MONEY_NUMBER_1` / `_2` | Vos deux numéros marchands Orange Money |
| `MOOV_MONEY_NUMBER` / `WAVE_NUMBER` | Vos numéros Moov Money et Wave |
| `ORANGE_USSD_TEMPLATE` | Code marchand (`*144*10*{numero}*{montant}#`) |

Ces numéros ne servent qu'à amorcer la base : une fois `init_catalogue` passé,
les comptes d'encaissement se gèrent **depuis l'administration, pays par pays**
(Pays & villes → Comptes d'encaissement).
| `PAYOUT_DELAY_DAYS` | Délai avant qu'un vendeur puisse retirer ses gains |

---

## Paiements

L'application ne connaît qu'une interface : `payments/providers/base.py`.
Deux implémentations sont fournies.

**`manual`** (par défaut) — l'application affiche au client le **code marchand
complet, montant inclus** (`*144*10*64691208*23100#`) avec un bouton qui le
compose directement. Le client valide avec son code secret, recopie l'identifiant
du SMS, et vous confirmez depuis `/paiement/admin/transactions/`. Zéro frais,
zéro contrat, opérationnel tout de suite. Vos deux numéros sont proposés.

**`cinetpay`** — paiement automatique Orange Money, Moov Money, Wave et carte.
Renseignez `CINETPAY_API_KEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET_KEY` et
passez `PAYMENT_PROVIDER=cinetpay`. Rien d'autre à changer dans le code.

URL de notification à déclarer chez l'agrégateur :
`https://votre-domaine/paiement/webhook/`

Ajouter un nouvel opérateur = un fichier dans `payments/providers/` et une ligne
dans `REGISTRY`.

### Tâche quotidienne

```bash
python manage.py liberer_gains
```

Rend disponibles au retrait les gains dont le délai de sécurité est écoulé.
À planifier une fois par jour (tâche cPanel ou cron).

---

## Mise en production (cPanel / LWS)

La procédure complète est dans **`GUIDE_DEPLOIEMENT_LWS.md`** : sous-domaine,
base MySQL, application Python Passenger, HTTPS, tâche quotidienne, sauvegardes
et dépannage.

En résumé :

1. `faire_le_paquet.bat` sur votre ordinateur → un ZIP de 2 Mo sans secrets.
2. Le téléverser et l'extraire dans le dossier de l'application sur cPanel.
3. `pip install -r requirements.txt`
4. `python deploiement/configurer.py` — écrit le `.env`, crée les dossiers
   publics et y pose la protection `.htaccess`.
5. `python deploiement/mise_en_ligne.py` — migrations, catalogue, statiques,
   puis rapport de vérification.
6. Créer l'administrateur, poser les deux `.htaccess`, redémarrer l'application.

À tout moment : `python manage.py verifier_production` dit ce qui manque.

---

## Multi-pays

EazyMarket n'est pas un site mondial unique : c'est une place de marché
**locale, répliquée pays par pays**. Chaque pays a ses vendeurs, ses artisans,
ses livreurs, sa monnaie, ses tarifs et ses numéros d'encaissement. Un acheteur
de Ouagadougou voit le catalogue du Burkina ; un acheteur d'Abidjan voit celui
de Côte d'Ivoire. Un livreur ne reçoit que les courses de son pays.

Douze pays sont créés d'avance, tous fermés sauf le Burkina Faso. Ouvrir un pays
se fait entièrement depuis l'administration (Pays → cocher « Ouvert au public »,
ajouter un compte d'encaissement local) — **aucun code à modifier**.

Voir `GUIDE_ADMIN.md` § 3 ter.

---

## Modèle économique en un coup d'œil

| Qui | Paie quoi |
|---|---|
| **Vendeur** | 2 annonces offertes, puis 5 000 F les 10 emplacements (définitifs) + 5 % de commission ajoutée au prix affiché |
| **Artisan** | 1 000 F / 3 mois pour apparaître dans l'annuaire, **0 %** sur ses chantiers |
| **Client** | Tout est gratuit : catalogue, fiches, devis. 200 F seulement s'il veut le numéro direct d'un artisan (le premier est offert) |
| **Livreur** | Rien. Activation en partageant le lien à 3 personnes, validées par un administrateur |
| **Boutique officielle** | Le compte de l'équipe publie sans limite et sans commission (case à cocher dans l'admin) |

Un même compte peut cumuler les activités : vendre, livrer et proposer ses
services. Le menu de l'avatar propose « Ajouter une activité » pour ce qui
manque — pas besoin de créer un second compte.

Le vendeur saisit ce qu'il veut **toucher** ; la commission est ajoutée puis le
total est arrondi au palier supérieur, pour un prix affiché propre :
22 000 F saisis → 23 100 F affichés → 22 000 F encaissés par le vendeur.

Détail et chiffres dans `MODELE_ECONOMIQUE.md`.

---

## Documents utiles

- `MODELE_ECONOMIQUE.md` — les cinq sources de revenus, les chiffres, l'encaissement Orange Money
- `GUIDE_ADMIN.md` — accéder au back-office, vérifier les utilisateurs, valider les paiements
- `IDENTITE_VISUELLE.md` — charte graphique et prompts de génération du logo
- `IDEES.md` — fonctionnalités à ajouter, classées par rapport valeur / effort
- `GUIDE_DEPLOIEMENT_LWS.md` — mise en ligne pas à pas sur LWS / cPanel
