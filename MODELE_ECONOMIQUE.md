# EazyMarket — modèle économique et encaissement

Version du 4 septembre 2026. Ce document décrit **ce qui est réellement codé
dans l'application**, ce que ça rapporte, et comment l'argent arrive sur vos
numéros Orange Money.

---

## 1. Les six sources de revenus

| Source | Qui paie | Combien | Où c'est réglé |
|---|---|---|---|
| **Pack d'annonces** | Le vendeur | 5 000 FCFA les 10 annonces, à vie — **obligatoire pour ouvrir** | `SHOP_PACK_PRICE` |
| **Commission sur ventes** | L'acheteur (incluse dans le prix) | 5 %, minimum 100 F | `COMMISSION_RATE` |
| **Abonnement artisan** | L'artisan | 1 000 FCFA / 3 mois | `ARTISAN_SUB_PRICE` |
| **Déblocage de contact** | Le client | 200 FCFA par artisan | `CONTACT_UNLOCK_PRICE` |
| **Mise en avant** | L'artisan ou le vendeur | 2 000 FCFA / 7 jours | `ARTISAN_BOOST_PRICE` |
| **Emplacements vidéo** | Le vendeur ou l'artisan | 500 FCFA les 5, à vie | `VIDEO_PACK_PRICE` |

Tout est modifiable dans le fichier `.env`, sans toucher au code.

### 1.1 Le vendeur : 2 annonces offertes, puis 5 000 F les 10

Un nouveau vendeur publie **2 annonces gratuitement**. C'est assez pour tester,
pas assez pour s'installer. Quand il veut agrandir, il achète un pack de 10
emplacements à 5 000 FCFA. Ces emplacements sont **acquis définitivement** — ce
n'est pas un abonnement, rien n'expire, rien n'est prélevé automatiquement.
Supprimer une annonce libère son emplacement.

Pourquoi 2 et pas 0 : un vendeur qui n'a jamais rien publié ne sait pas ce qu'il
achète. Les deux premières annonces lui montrent l'écran de commande, les vues,
et la première question d'un client. C'est là qu'il décide de payer.
Vous pouvez passer à 0 en changeant `SHOP_FREE_SLOTS` — mais attendez d'avoir
des clients sur le site.

### 1.1 bis Depuis septembre 2026 : plus d'essai gratuit

**Ce qui change.** Le vendeur ne publie plus deux annonces avant de payer. Il
remplit sa fiche, puis règle le pack de 10 emplacements à 5 000 FCFA — et
c'est ce règlement qui ouvre la boutique. `SHOP_FREE_SLOTS` vaut désormais 0.

**Ce que vous gagnez.** Chaque boutique rapporte dès le premier jour, et vous
ne portez plus le coût des comptes ouverts « pour voir » qui n'ont jamais rien
vendu.

**Ce que vous perdez, et qu'il faut regarder en face.** L'essai gratuit était
ce qui remplissait le catalogue au démarrage. Sans lui, un vendeur doit payer
avant d'avoir vu une seule vente arriver — c'est un pari qu'il ne fera que
s'il vous croit déjà. Trois choses réduisent ce frein :

1. **La fiche est enregistrée avant le paiement.** Le vendeur qui s'arrête au
   moment de payer n'est pas perdu : ses informations sont là, il apparaît
   dans l'administration, et un message WhatsApp suffit à le relancer.
2. **Le prix est annoncé avant le formulaire**, pas découvert à la fin. Une
   mauvaise surprise coûte plus cher qu'un prix affiché d'emblée.
3. **Le mot « définitif » fait le travail** : 5 000 FCFA une fois, pour
   toujours, ce n'est pas un abonnement. C'est l'argument à répéter partout.

**Le levier si ça bloque.** Vous n'avez pas besoin de moi pour revenir en
arrière : `SHOP_FREE_SLOTS=2` dans le `.env` rétablit l'essai gratuit, sans
toucher au code. Vous pouvez aussi offrir un pack au cas par cas depuis
l'administration (Profils → *Emplacements achetés*), par exemple pour un
vendeur qui vous amène du monde.

**Les boutiques déjà ouvertes ne sont pas touchées** : elles restent actives
avec les emplacements qu'elles avaient. Seules les nouvelles passent par la
caisse.

---

### 1.2 La commission : le prix arrondi règle votre objection

Votre remarque était juste : afficher **1 050 F** est laid, et retirer 50 F au
commerçant sur un produit à 1 000 F l'est tout autant.

La solution codée : on ajoute la commission **puis on arrondit le total au
palier supérieur**. Le vendeur touche exactement son prix, le client voit un
prix de marché normal.

| Le vendeur saisit | Le client voit | Vous gardez | Taux réel |
|---:|---:|---:|---:|
| 1 000 F | **1 100 F** | 100 F | 10 % |
| 2 500 F | **2 700 F** | 200 F | 8,0 % |
| 7 500 F | **7 900 F** | 400 F | 5,3 % |
| 22 000 F | **23 100 F** | 1 100 F | 5,0 % |
| 78 000 F | **82 000 F** | 4 000 F | 5,1 % |
| 195 000 F | **205 000 F** | 10 000 F | 5,1 % |

Aucun prix ne finit par 50 ou 25. Le plancher de 100 F protège les tout petits
paniers, sur lesquels une commission de 5 % ne couvrirait même pas les frais.

Dans son tableau de bord, le vendeur voit le calcul **en direct** pendant qu'il
saisit son prix : « vous saisissez 22 000 → le client voit 23 100 → vous touchez
22 000 ». Il n'y a rien à cacher, donc rien à expliquer.

### 1.3 L'artisan : 1 000 F tous les trois mois

Profil gratuit à créer, avec photos de réalisations. **Mais il n'apparaît dans
l'annuaire qu'une fois l'abonnement payé** — 1 000 FCFA pour 90 jours, soit
500 F par mois, soit environ 17 F par jour. Aucune commission sur ses chantiers.

Sur sa page d'abonnement, l'artisan non abonné voit écrit noir sur blanc : « votre
fiche existe mais n'apparaît pas dans les recherches, personne ne peut vous
trouver ». C'est la phrase qui convertit.

> **Le levier de lancement.** Tant que l'annuaire est vide, personne ne le
> consulte, donc personne ne veut payer pour y figurer. Mettez
> `ARTISAN_FREE_LAUNCH=True` dans le `.env` : tous les profils deviennent
> visibles gratuitement. Remplissez l'annuaire pendant deux à trois mois,
> laissez les premiers chantiers se faire, puis repassez à `False`. Les artisans
> qui auront décroché un client paieront sans discuter — les autres partiront, et
> ce n'est pas grave.

### 1.4 Le déblocage de contact à 200 F : votre meilleure idée

Vous aviez raison de repérer le trou : sans cela, l'artisan met son numéro, le
client l'appelle, et vous n'avez rien.

Ce qui est codé :

- La fiche de l'artisan est **entièrement consultable** — photo, métier,
  quartier, réalisations, avis, fourchette de prix. Seul le numéro est masqué
  (`70 11 11•• ••`).
- Deux boutons côte à côte :
  - **« Voir le numéro — 200 FCFA »** pour appeler tout de suite ;
  - **« Demander un devis — gratuit »**, qui reste entièrement gratuit.
- Le **premier contact de chaque nouveau client est offert** (`CONTACT_FREE_UNLOCKS=1`).
  Il découvre la valeur avant de payer, et il revient.
- Un déblocage est valable **90 jours pour cet artisan** : le client ne paie
  jamais deux fois pour le même professionnel.

Pourquoi ça tient : 200 FCFA, c'est le prix d'un sachet d'eau et deux beignets.
Personne ne renonce à faire réparer sa plomberie pour 200 F, mais 200 F × 1 000
mises en relation par mois = **200 000 FCFA**, sans avoir rien prélevé à
personne d'important.

Et cela fait aussi le ménage : un client qui paie 200 F appelle vraiment. Les
artisans reçoivent moins d'appels perdus, et ils s'en aperçoivent.

> **Le risque à surveiller.** Les deux parties peuvent se donner rendez-vous hors
> plateforme la fois suivante. C'est inévitable et ce n'est pas grave : votre
> revenu vient du **flux de nouveaux besoins**, pas de la relation une fois
> établie. Ne cherchez jamais à empêcher ça — vous perdriez la confiance des
> deux côtés.

### 1.5 La vidéo : 3 offertes, puis 500 F les 5

**Pourquoi ça se vend tout seul.** Une photo peut être trouvée sur internet ;
une vidéo de quinze secondes où l'on tourne autour de l'objet, non. Pour un
client qui doit payer avant de recevoir, c'est la preuve la plus convaincante
qu'il existe. Pour un artisan, c'est la seule façon de montrer un chantier
en mouvement. Le vendeur n'a pas besoin qu'on lui explique l'intérêt : il voit
ses concurrents avec une vidéo et il en veut une.

**Pourquoi seulement 3 offertes.** Ce n'est pas de l'avarice, c'est du disque.
Une vidéo de 30 secondes pèse environ 12 Mo :

| Vidéos offertes | 200 vendeurs | 500 vendeurs | 1 000 vendeurs |
|---|---|---|---|
| 3 | 7 Go | 18 Go | 36 Go |
| 10 | 24 Go | 60 Go | 120 Go |

Sur un hébergement mutualisé, la deuxième ligne fait sauter le compte — et la
bande passante coûte encore plus cher que le disque. Trois emplacements
suffisent largement à un vendeur qui met en avant ses trois meilleurs articles.

**La porte de sortie gratuite : le lien.** Un vendeur peut coller l'adresse
d'une vidéo TikTok, YouTube, Facebook ou Instagram. Ça ne consomme aucun
emplacement, c'est illimité, et ça ne vous coûte rien du tout. Trois bonnes
raisons de le proposer franchement :

1. Beaucoup de vos vendeurs filment déjà pour TikTok — vous ne leur demandez
   aucun effort supplémentaire.
2. Ça sert votre objectif principal : le maximum d'utilisateurs, pas le
   maximum de francs par utilisateur.
3. Celui qui a une audience TikTok l'amène chez vous.

Le pack payant ne concerne donc que les vidéos hébergées chez vous, c'est-à-dire
celles qui vous coûtent réellement de l'argent. C'est un tarif honnête : le
vendeur paie une ressource, pas une permission.

**Ce qu'il ne faut pas faire.** Ne rendez jamais la vidéo obligatoire, et ne
laissez jamais une vidéo se lancer toute seule. La connexion se paie au
mégaoctet ici : un visiteur dont le forfait fond en parcourant votre catalogue
ne revient pas. Sur le site, rien ne se télécharge tant qu'on n'a pas cliqué.

**Réglages** — tout est dans le `.env`, sans toucher au code :
`VIDEO_FREE_SLOTS`, `VIDEO_PACK_SIZE`, `VIDEO_PACK_PRICE`, `VIDEO_MAX_SECONDS`,
`VIDEO_MAX_MB`, `VIDEO_MAX_PAR_FICHE`. Si votre hébergement grossit, passez
`VIDEO_FREE_SLOTS` à 10 : une ligne à changer.

---

### 1.6 Le circuit de l'argent, verrouillé

Depuis le 14 septembre 2026, le vendeur n'est plus payé à la confirmation mais
**à la livraison**. La différence est tout sauf théorique : avant, un vendeur
pouvait cliquer « j'ai le produit », ne rien livrer, et voir son argent devenir
retirable trois jours plus tard. Seul votre contrôle manuel au moment du
versement l'en empêchait — ce qui tient à dix commandes par jour, pas à cent.

Le client dispose de 3 jours après la livraison pour signaler qu'il n'a rien
reçu ; l'argent du vendeur est alors rebloqué et vous arbitrez.

Et le client annulé choisit désormais : garder son avoir, ou recevoir la somme
sur son mobile money. C'est une dépense pour vous quand il choisit l'argent,
mais c'est le prix de la confiance : un premier acheteur à qui l'on impose un
bon d'achat ne revient pas, et il le raconte.

---

## 2. Ce que ça donne en chiffres

Hypothèses volontairement prudentes, Ouagadougou seul.

### Mois 6

| Source | Base | Revenu mensuel |
|---|---|---|
| Packs d'annonces | 25 vendeurs achètent 1 pack | **125 000 F** |
| Commission produits | 200 commandes × 20 000 F = 4 000 000 F de volume | **210 000 F** |
| Abonnements artisans | 250 profils, 40 % abonnés = 100 × 1 000 F / 3 mois | **33 000 F** |
| Déblocages de contact | 600 × 200 F | **120 000 F** |
| Marge livraison | 200 courses × 300 F | **60 000 F** |
| Mises en avant | 10 × 2 000 F | **20 000 F** |
| **Total** | | **≈ 585 000 F / mois** |

### Mois 12 (volumes ×2,5, taux d'abonnement à 55 %)

| Source | Revenu mensuel |
|---|---|
| Packs d'annonces | 200 000 F |
| Commission produits | 525 000 F |
| Abonnements artisans | 170 000 F |
| Déblocages de contact | 350 000 F |
| Marge livraison | 150 000 F |
| Mises en avant | 60 000 F |
| **Total** | **≈ 1 455 000 F / mois** |

**Charges à retrancher :** frais d'encaissement mobile money (2 à 3 % du volume
collecté quand vous passerez à un agrégateur), hébergement (10 à 20 000 F/mois),
et votre temps.

**Ce qu'il faut lire dans ce tableau :** aucune source ne dépasse 40 % du total.
C'est exactement ce qu'on veut. Si un opérateur change ses tarifs ou si les
artisans boudent l'abonnement, vous ne coulez pas.

---

## 3. Se faire de l'argent sans taxer cher — 8 pistes

Votre principe est le bon : **beaucoup de petits paiements volontaires plutôt
qu'un gros prélèvement obligatoire.** Voici comment le pousser plus loin.

### 3.1 Le badge « Vérifié » à 2 000 F — payé avec plaisir

Contrôle de la pièce d'identité, appel téléphonique, et un badge vert sur la
fiche. Sur un marché où la confiance est rare, ce badge fait la différence entre
être appelé et être ignoré. Les artisans sérieux **veulent** payer pour se
distinguer des autres — c'est le contraire d'une taxe. Paiement unique, marge
quasi totale. Le champ existe déjà (`is_verified`), il ne manque que le tunnel
de paiement.

### 3.2 La remontée d'annonce à 200 F

Un vendeur dont le produit est descendu dans la liste paie 200 F pour le
remettre en tête de sa catégorie pendant 3 jours. Achat d'impulsion, effet
visible immédiatement, montant indolore. C'est le mécanisme qui rapporte le plus
sur les sites de petites annonces africains — bien plus que les abonnements.

### 3.3 La publicité locale : faire payer ceux qui ne vendent pas chez vous

Une bannière en haut de la page « Services — Ouaga 2000 » vendue 10 000 F le
mois à une quincaillerie du quartier. Ce n'est pas de l'argent pris à vos
utilisateurs, c'est de l'argent pris à des commerces qui veulent votre audience.
À partir de quelques milliers de visiteurs par mois, c'est votre revenu le plus
rentable — zéro coût variable.

### 3.4 Les cartes de visite avec QR code

Vous imprimez, pour un artisan, 100 cartes portant son nom et un QR code vers sa
fiche EazyMarket. 5 000 F, dont la moitié de marge. Vous vendez un objet
physique dont il a réellement besoin, et **chaque carte distribuée ramène un
client sur votre application**. C'est de la publicité que vos utilisateurs vous
paient pour faire.

### 3.5 L'achat groupé de quartier

Cinq voisins commandent ensemble un sac de riz ou du ciment ; vous négociez le
prix de gros, le client paie moins cher qu'au détail, et vous gardez l'écart.
Personne n'a l'impression de payer une commission — tout le monde a gagné. Et ça
crée une raison de revenir chaque semaine.

### 3.6 Le séquestre sur les gros chantiers

Pour un devis au-delà de 100 000 FCFA : le client verse à la plateforme,
l'argent est libéré à la réception des travaux. Vous prenez 3 %. C'est la seule
commission acceptable sur un service, parce qu'elle achète une garantie réelle
— et c'est justement sur les gros montants que la confiance manque le plus.
L'infrastructure (`Transaction`, `WalletEntry`) est déjà en place.

### 3.7 Le parrainage payant entre professionnels

Un artisan qui en fait abonner trois gagne deux mois offerts. Vous « payez » en
service, pas en argent, et vos utilisateurs deviennent vos commerciaux. Un
menuisier connaît tous les menuisiers de son quartier.

### 3.8 La formation courte

« Photographier ses produits avec un téléphone », « répondre à un client sans
perdre la vente » : 2 000 F la session, en salle ou sur WhatsApp. Vous avez déjà
l'audience et la crédibilité. Vos vendeurs formés publient de meilleures
annonces, donc vendent plus, donc vous rapportent plus en commission. Le revenu
se paie deux fois.

### Ce qu'il ne faut PAS faire

- **Faire payer la recherche ou la consultation.** Le catalogue et les fiches
  doivent rester entièrement gratuits, toujours. Vous vendez l'accès à
  l'action, jamais l'accès à l'information.
- **Monter le déblocage au-dessus de 500 F.** Au-delà, le client appelle son
  cousin qui connaît quelqu'un, et vous perdez tout.
- **Prendre une commission sur les prestations d'artisans hors séquestre.** Elle
  est incontrôlable, elle pousse hors plateforme, et elle détruit votre
  meilleur argument de recrutement.

---

## 4. Comment l'argent arrive chez vous

### Vos quatre comptes d'encaissement

Trois opérateurs, quatre numéros, tous actifs :

| Opérateur | Numéro | Ce que voit le client |
|---|---|---|
| Orange Money | +226 64 69 12 08 *(WhatsApp)* | `*144*10*64691208*MONTANT#` |
| Orange Money | +226 46 31 90 94 | `*144*10*46319094*MONTANT#` |
| Moov Money | +226 02 09 66 85 | menu `*555#` |
| Wave | +226 77 55 20 87 *(WhatsApp)* | application Wave |

Les deux numéros WhatsApp figurent en pied de page, l'un sous l'autre : quand
vous n'êtes pas devant le premier, le second prend le relais.

Ces numéros vivent désormais **en base de données**, pas seulement dans le
`.env` (Administration → Pays & villes → Comptes d'encaissement). C'est ce qui
permet d'avoir des numéros différents dans chaque pays sans toucher au code.

### Ce que voit le client

À l'étape de paiement, l'application génère **le code marchand complet, montant
inclus** :

> **`*144*10*64691208*23100#`**
> [ Composer ]  [ Copier le code ]

Sur téléphone, le bouton « Composer » ouvre directement le clavier avec le code
prérempli. Le client n'a plus qu'à valider avec son code secret Orange Money. Il
ne peut ni se tromper de numéro, ni se tromper de montant — c'est ce qui vous
évitera l'essentiel des litiges.

Les quatre comptes sont proposés, regroupés par opérateur : si un numéro est
saturé ou en dérangement, le client en choisit un autre sans quitter la page.

Ensuite le client colle l'identifiant de transaction reçu par SMS, et un bouton
**« Prévenir sur WhatsApp »** lui permet de vous alerter sur le
+226 64 69 12 08. Vous validez depuis `/paiement/admin/transactions/` et tout
s'enchaîne : commande payée, stock décrémenté, vendeur crédité, abonnement
activé, contact débloqué.

### Deux précautions

1. **Ouvrez un compte Orange Money Marchand** (en boutique Orange, avec votre
   pièce d'identité) plutôt que d'utiliser un compte particulier. Les plafonds
   d'un compte particulier sont vite atteints par une activité commerciale, et
   un blocage en pleine journée de vente vous coûterait plus cher que la
   démarche.
2. **Sur une commande de 23 100 F, 22 000 F ne vous appartiennent pas.** Ils
   appartiennent au vendeur. Ne dépensez jamais le solde de vos numéros
   marchands comme si c'était votre argent — tenez un cahier ou un tableur avec,
   chaque semaine : ce que vous avez encaissé, ce que vous devez aux vendeurs,
   ce qui vous reste vraiment.

### Quand passer à l'automatique

Le mode manuel tient jusqu'à une dizaine de transactions par jour. Au-delà, vous
y passerez vos soirées. Le connecteur **CinetPay** est déjà écrit
(`payments/providers/cinetpay.py`) : trois clés dans le `.env`,
`PAYMENT_PROVIDER=cinetpay`, et le paiement devient automatique pour Orange
Money, Moov Money, Wave et la carte bancaire. Comptez 2 à 3 % de frais, un
dossier avec RCCM et NIF, et quelques jours d'instruction.

L'API Orange Money en direct (environ 50 000 F d'ouverture, 25 000 F par mois,
1 à 1,6 % de commission) ne devient intéressante qu'au-delà de **2 millions de
FCFA encaissés par mois** — et elle ne couvre que les clients Orange. Restez sur
l'agrégateur, et négociez une remise au volume.

---

## 4 bis. S'étendre à d'autres pays

L'application est prête techniquement : chaque pays est une place de marché
locale, avec sa monnaie, ses tarifs, ses vendeurs, ses artisans, ses livreurs et
ses numéros d'encaissement. Ouvrir un pays se fait depuis l'administration, sans
toucher au code.

**Mais ouvrir un pays n'est pas un problème de logiciel.** Il faut sur place :

1. **Un moyen d'encaisser.** Un numéro mobile money local, ou un agrégateur qui
   couvre le pays. Sans cela, personne ne peut payer — et c'est déjà le point
   bloquant hors zone FCFA (Ghana, Nigeria : autre monnaie, autres opérateurs).
2. **Des livreurs.** Un catalogue que personne ne peut livrer ne sert à rien.
   C'est la contrainte la plus dure, et elle est purement humaine.
3. **Quelqu'un qui répond au téléphone dans le pays.** Valider les paiements,
   arbitrer un litige, appeler les répondants d'un livreur : cela ne se fait pas
   à distance.
4. **Une base de départ.** Une vingtaine de vendeurs et une dizaine d'artisans
   dans une seule ville. En dessous, le visiteur ne trouve rien et ne revient pas.

**L'ordre que je vous conseille :**

- **Aujourd'hui** — Ouagadougou. Densifiez quartier par quartier jusqu'à ce que
  la recherche « plombier » donne cinq résultats sérieux.
- **Ensuite** — Bobo-Dioulasso, puis les autres villes burkinabè. Même pays,
  même monnaie, mêmes numéros : rien à changer, tout à gagner en volume.
- **Puis** — un pays voisin de la zone FCFA (Côte d'Ivoire, Mali, Niger, Togo,
  Bénin, Sénégal). Même monnaie, mêmes opérateurs, souvent quelqu'un de votre
  réseau sur place. C'est de loin le saut le moins coûteux.
- **Plus tard** — hors zone FCFA. Nouvelle monnaie, nouveaux opérateurs,
  nouvelle réglementation. Ne vous y attaquez qu'avec un vrai correspondant local.

**Ce qu'il ne faut pas faire :** ouvrir dix pays d'un coup. Dix vitrines vides
valent moins qu'une seule pleine — et un visiteur déçu ne revient jamais. La
livraison internationale (douanes, coûts, délais, litiges) est un métier à part
entière : ne la promettez pas tant que vous ne l'avez pas testée vous-même.

**Ce que ça change pour vos revenus :** rien dans le modèle, tout dans le
volume. Chaque pays reproduit les mêmes cinq sources. Deux pays à mi-régime
rapportent moins qu'un pays plein — mais un pays plein reproduit à l'identique
dans le pays voisin double le chiffre sans rien réinventer.

---

## 4 ter. Votre propre boutique

Vous pouvez vendre sur votre plateforme : cochez **Emplacements illimités** et
**Boutique officielle** sur votre profil dans l'administration. Annonces sans
limite, commission à 0 % (elle n'aurait aucun sens : l'argent revient dans votre
poche de toute façon), et le prix saisi est le prix affiché.

Deux garde-fous, parce que c'est un vrai risque commercial :

- **Jouez franc-jeu.** Le badge « Boutique officielle » est visible sur vos
  fiches. Un vendeur qui découvre que le patron vend en douce sous un faux nom
  s'en va — et il le raconte au marché.
- **Ne vous mettez pas en avant contre eux.** Le jour où vos meilleures places
  sont occupées par vos propres produits, votre place de marché redevient une
  simple boutique en ligne. Votre valeur, c'est le nombre de vendeurs, pas votre
  propre stock.

---

## 5. Comment les vendeurs récupèrent leur part

1. Commande payée → le vendeur est crédité de `sous-total − commission`, en
   statut **« en attente »**.
2. **3 jours après la livraison** (`PAYOUT_DELAY_DAYS`), la somme devient
   **disponible**. Ce délai vous permet de rembourser un client mécontent — et
   c'est lui qui vous autorise à garantir l'acheteur.
3. Le vendeur demande un retrait à partir de 5 000 FCFA.
4. Vous voyez la demande dans `/paiement/admin/retraits/`, vous faites le
   transfert Orange Money, vous cliquez « Versé ».

Un solde de portefeuille n'est jamais un champ modifié à la main : c'est la
somme des écritures comptables. Impossible de perdre de l'argent en route, et
tout est auditable.

**Tâche quotidienne :** `python manage.py liberer_gains`

---

## 6. Sources

- [Orange Business Burkina Faso — paiement en ligne](https://www.orange.bf/business/fr/orange-money-paiement-en-ligne.html)
- [Orange Business Burkina Faso — paiement marchand](https://www.orange.bf/business/fr/orange-money-paiement-marchand.html)
- [Grille tarifaire Orange Money Burkina Faso](https://www.orange.bf/fr/tarifs-orange-money.html)
- [Ouvrir un compte marchand Orange Money Burkina Faso (2026)](https://simiz.io/blog/ouvrir-compte-marchand-orange-money-burkina-faso)
- [CinetPay](https://cinetpay.com/products/payments) · [LigdiCash](https://www.ligdicash.com/)
- [Comparatif des solutions de paiement UEMOA](https://pandore.co/en/paiement-en-ligne-uemoa-les-meilleures-solutions-en-2025/)

*Les tarifs des prestataires sont des ordres de grandeur publics. Demandez une
grille écrite avant de signer.*
