# Guide de l'administrateur EazyMarket

Comment accéder au back-office, vérifier les utilisateurs, valider les paiements
et faire tourner la place de marché au quotidien.

---

## 0. « Je n'arrive pas à me connecter »

Dans neuf cas sur dix, c'est l'adresse. **L'administration Django est sur
`/django-admin/`**, pas sur `/admin/` :

    http://127.0.0.1:8000/django-admin/

(`/admin/` y renvoie désormais automatiquement, mais l'adresse exacte reste
`/django-admin/`.)

Ne confondez pas avec la connexion du site — `/compte/connexion/` — qui sert à
tout le monde. Votre compte administrateur fonctionne aussi là, et vous y
trouverez le **Pilotage** dans le menu de votre avatar.

Si l'adresse n'est pas en cause, une commande fait le diagnostic :

```bash
venv\Scripts\activate
python manage.py admin_reset
```

Elle liste vos comptes administrateurs et signale ce qui cloche (compte
désactivé, pas superutilisateur, jamais connecté). Pour reprendre la main :

```bash
python manage.py admin_reset --user EazyMarket --mdp NouveauMotDePasse
python manage.py admin_reset --creer patron --mdp UnMotDePasseSolide   # nouveau compte
```

Deux autres causes possibles :

- **Le serveur ne tourne pas.** La page ne s'affiche pas du tout : lancez
  `run_server.bat` et laissez la fenêtre ouverte.
- **La base a été réinitialisée.** Votre ancien compte a disparu avec elle —
  recréez-le avec `--creer`.

---

## 1. Créer votre compte administrateur

Une seule fois, dans le dossier du projet :

```bash
venv\Scripts\activate
python manage.py createsuperuser
```

On vous demande un nom d'utilisateur, un e-mail et un mot de passe. **Prenez un
vrai mot de passe** : ce compte voit tout, y compris les pièces d'identité et les
numéros de téléphone de vos utilisateurs.

Pour changer le mot de passe plus tard :

```bash
python manage.py changepassword votre_nom_utilisateur
```

---

## 2. Les deux portes d'entrée

Vous avez **deux back-offices**, complémentaires.

### A. Le pilotage — `/compte/pilotage/`

C'est votre écran de tous les jours, dans le design du site. Il montre :

- le volume d'affaires, le revenu des commissions, celui des abonnements ;
- le nombre d'utilisateurs, de vendeurs, d'artisans, de produits, de commandes ;
- les dernières commandes, les meilleures ventes, les meilleurs vendeurs ;
- des raccourcis vers les trois écrans d'action ci-dessous.

Accessible depuis votre menu (avatar en haut à droite → **Pilotage**), pour tout
compte marqué « équipe » (`is_staff`).

### B. L'administration Django — `/django-admin/`

C'est la salle des machines : **toutes** les données, modifiables une par une ou
en masse. Moins joli, beaucoup plus puissant. Vous y trouverez :

| Section | Ce que vous y faites |
|---|---|
| **Utilisateurs** | Chercher quelqu'un, réinitialiser un mot de passe, désactiver un compte |
| **Profils utilisateurs** | Voir le rôle, le téléphone, le quartier, cocher « vérifié » |
| **Artisans** | Vérifier l'identité, bloquer un profil, voir l'état d'abonnement |
| **Produits** | Modérer une annonce (décocher « validé » la retire du site) |
| **Commandes** | Voir le détail, l'historique, corriger un statut |
| **Transactions** | Confirmer ou refuser un paiement, en masse |
| **Portefeuilles / Retraits** | Voir les soldes, marquer un retrait comme versé |
| **Dossiers livreurs** | Voir les personnes parrainées et la pièce d'identité |
| **Contacts débloqués** | Qui a payé pour joindre quel artisan |
| **Pays & villes** | Ouvrir un pays, régler ses tarifs, ajouter ses numéros d'encaissement |

Chaque liste a une **barre de recherche** et des **filtres** dans la colonne de
droite. Pour retrouver un utilisateur à partir de son numéro de téléphone :
Profils utilisateurs → recherche → tapez le numéro.

---

## 3. Les trois écrans d'action quotidiens

### Valider les paiements — `/paiement/admin/transactions/`

Le plus important. Tant que vous encaissez à la main, c'est ici que l'argent
devient réel.

1. Le client a payé sur un de vos numéros et déclaré son identifiant de transaction.
2. Vous ouvrez l'écran, onglet **À vérifier**.
3. Vous comparez avec vos SMS Orange Money : montant, heure, numéro payeur.
4. **Valider** → la commande devient payée, le stock baisse, le vendeur est
   crédité, l'abonnement s'active, le contact se débloque — tout s'enchaîne seul.
5. **Refuser** si vous ne retrouvez pas le paiement. Le client est notifié.

> Ne validez jamais sans avoir vu l'argent arriver. C'est la seule règle qui
> compte : une validation à tort, c'est de l'argent que vous devrez au vendeur.

### Verser les retraits — `/paiement/admin/retraits/`

Un vendeur demande un retrait. Vous faites le transfert Orange Money depuis votre
téléphone, puis vous collez l'identifiant du transfert et cliquez **Versé**.
L'écriture de débit se crée automatiquement : le solde ne peut pas se
désynchroniser.

### Activer les livreurs — `/livraison/dossiers/`

Un livreur a partagé le lien à 3 personnes et envoyé son dossier. Vous voyez la
liste des contacts et sa pièce d'identité. **Appelez au moins deux d'entre eux**,
notez ce qu'ils disent, puis validez ou refusez.

---

## 3 bis. Votre propre boutique

Vous pouvez vendre sur votre plateforme, sans limite et sans commission — les
revenus vous reviennent de toute façon.

Django admin → **Profils utilisateurs** → votre compte → cochez :

- **Emplacements illimités** : aucune limite d'annonces (automatique pour tout
  compte « équipe ») ;
- **Boutique officielle** : commission à 0 % sur vos produits, et un badge
  « Boutique officielle » sur votre vitrine et vos fiches.

Le prix que vous saisissez est alors le prix affiché, sans majoration.

Pensez à renseigner un **nom de boutique** dans le même écran : c'est lui qui
apparaît publiquement, pas votre nom d'utilisateur.

> Un mot d'honnêteté : vendre vous-même sur votre place de marché est courant
> (Amazon et Jumia le font), mais vos vendeurs le verront. Ne vous mettez pas en
> avant au détriment des leurs — si les commerçants ont le sentiment de
> concurrencer le patron, ils partent. Le badge « Boutique officielle » sert
> justement à jouer franc-jeu.

---

## 3 ter. Ouvrir un nouveau pays

L'application est prête pour l'international : chaque pays est une place de
marché locale, avec ses vendeurs, ses artisans, ses livreurs, sa monnaie et ses
numéros d'encaissement. Un acheteur ne voit que le catalogue de son pays.

Douze pays sont déjà créés (Burkina, Côte d'Ivoire, Mali, Sénégal, Niger, Bénin,
Togo, Guinée, Ghana, Nigeria, Cameroun, Tchad), tous **fermés** sauf le Burkina.

Pour en ouvrir un :

1. Django admin → **Pays** → choisissez le pays.
2. Vérifiez la **devise** et la **ville principale**.
3. Ajustez si besoin les **tarifs locaux** (laisser 0 = valeurs du `.env`).
4. Ajoutez au moins un **compte d'encaissement** : opérateur, numéro local,
   code à composer s'il en existe un. Sans cela, personne ne pourra payer.
5. Ajoutez les **villes** que vous couvrez.
6. Cochez **« Ouvert au public »** et enregistrez.

Le pays apparaît alors dans le sélecteur en haut à droite et en pied de page.

**Ce que le code ne fera pas à votre place :** trouver des vendeurs, des
livreurs et un numéro pour encaisser sur place. Un pays sans livreurs, c'est un
catalogue que personne ne peut recevoir. Ouvrez un pays quand vous y avez
quelqu'un — pas avant.

---

## 3 quater. Un compte, plusieurs activités

Un même compte peut **vendre, livrer et proposer ses services** à la fois. Un
menuisier qui vend des meubles finis et prend des commandes sur mesure n'a pas à
créer deux comptes ; un vendeur qui a une moto peut livrer ses propres commandes.

Depuis le menu de l'avatar, chacun voit une section **« Ajouter une activité »**
avec ce qui lui manque encore : ouvrir une boutique, proposer ses services,
devenir livreur. Aucune de ces actions ne supprime les autres.

Dans l'administration, trois cases pilotent cela sur le profil :

| Case | Effet |
|---|---|
| **Rôle** | L'activité principale, celle qui décide de la page d'accueil après connexion |
| **Boutique active** (`is_store_active`) | Donne accès au tableau de bord vendeur |
| **Compte livreur activé** (`is_driver`) | Donne accès à l'espace livreur, quel que soit le rôle |

Un livreur ne peut **prendre des courses** qu'une fois son dossier validé
(case « Compte vérifié »). Tant qu'il ne l'est pas, il voit son dossier de
parrainage et rien d'autre.

---

## 4. Vérifier un utilisateur

**Un vendeur.** Django admin → Profils utilisateurs → cherchez son nom → cochez
« Compte vérifié ». Un badge apparaît sur sa boutique et sur ses fiches produit.

**Un artisan.** Django admin → Artisans → cochez « Identité vérifiée ». Demandez-lui
d'abord d'envoyer sa pièce d'identité (champ `id_document`), et appelez son
numéro : un artisan qui ne décroche pas ne sera jamais choisi par un client.

**Bloquer quelqu'un.** Artisans → cochez « Bloqué » : son profil disparaît de
l'annuaire sans que ses données soient perdues. Pour un compte entier :
Utilisateurs → décochez « Actif ».

---

## 5. Modérer les annonces

Chaque produit a une case **« Validé par la modération »**, cochée par défaut
pour ne pas freiner les vendeurs. La décocher retire l'annonce du site
immédiatement, sans la supprimer.

Passez en revue les nouvelles annonces une fois par jour :
Django admin → Produits → tri par date. Regardez surtout la photo et le prix ;
c'est là que se voient les annonces douteuses.

---

## 5 bis. Modérer les vidéos

C'est le point à surveiller le plus sérieusement : une photo choquante se
repère au premier coup d'œil, une vidéo non.

**Django admin → Vidéos.** La liste indique pour chacune le propriétaire, la
source (fichier envoyé, ou lien TikTok / YouTube), la durée et le poids.
Deux actions groupées : *Retirer du site* et *Remettre en ligne*.

Ce que vous regardez, dans l'ordre :

1. **Les vidéos hébergées récentes** — ce sont celles qui occupent votre
   disque, et les seules dont vous êtes vraiment responsable.
2. **Les liens externes** — vérifiez que l'adresse mène bien à la boutique ou
   au métier annoncé. Seules quatre plateformes sont acceptées (TikTok,
   YouTube, Facebook, Instagram), un lien vers autre chose est refusé
   automatiquement.

Retirer une vidéo ne supprime rien : elle disparaît du site, le vendeur la
voit marquée « retirée du site » dans son tableau de bord, et vous pouvez la
remettre en ligne à tout moment. Pour libérer réellement de l'espace disque,
il faut la **supprimer** — le fichier part avec.

**Surveillez l'espace.** cPanel → *Utilisation du disque*. Si ça monte trop
vite, baissez `VIDEO_FREE_SLOTS` dans le `.env` : les vendeurs pourront
toujours coller un lien TikTok, qui ne vous coûte rien.

---

## 6. La tâche quotidienne

Une fois par jour, pour rendre disponibles les gains des vendeurs dont le délai
de sécurité est écoulé :

```bash
python manage.py liberer_gains
```

Sur l'hébergement, cela se planifie dans les **tâches cron** du cPanel.
Si vous oubliez, personne ne perd d'argent — les vendeurs attendent simplement
plus longtemps avant de pouvoir retirer.

---

## 6 ter. L'argent : qui est payé, quand, et comment

**La règle, en une phrase :** le vendeur est payé quand le client a reçu, pas
quand le vendeur a promis.

Le parcours complet d'un paiement :

| Étape | Ce qui arrive à l'argent |
|---|---|
| Le client paie | La somme est chez vous. Rien n'est crédité à personne. |
| Le vendeur confirme sous 24 h | Sa part est inscrite à son solde, **bloquée sans date**. |
| Sans confirmation | Commande annulée, client recrédité automatiquement. |
| La commande est marquée **livrée** | Le compte à rebours de 3 jours démarre. |
| 3 jours plus tard | La somme devient retirable par le vendeur. |
| Le vendeur demande un retrait | La demande arrive chez vous. Vous versez, vous marquez « versé ». |

Tant que personne n'a marqué la livraison, **le vendeur n'est jamais payé**.
Un vendeur qui confirme sans livrer ne touche rien.

### Qui déclare la livraison

Trois personnes peuvent le faire, et **tant que personne ne le fait, le vendeur
n'est jamais payé** :

| Qui | Où | Effet |
|---|---|---|
| **Le client** | Sa commande → *« Oui, j'ai reçu ma commande »* | Le plus fiable. Pas de contestation possible ensuite. |
| **Le vendeur** | Mes ventes → *« Oui, remis au client »* | Le client garde 3 jours pour contester. |
| **Le livreur** | Son tableau de bord → *« Marquer livrée »* | Idem. |

Encouragez vos vendeurs à demander au client de confirmer depuis l'application :
c'est plus rapide pour eux, et ça leur évite la fenêtre de contestation.

Si une commande reste sans livraison déclarée, elle remonte au bout de 10 jours
dans `verifier_production`. Dans ce cas, appelez le vendeur : neuf fois sur dix
il a livré et n'a pas cliqué.

### Le client dit « je n'ai pas reçu »

Pendant les 3 jours qui suivent la livraison, le client a un bouton
**« Je n'ai pas reçu ma commande »** sur sa page de commande. S'il l'utilise :

- l'argent du vendeur est **immédiatement rebloqué**, même si l'échéance était proche ;
- le vendeur et vous recevez une notification ;
- la commande est marquée en litige.

**Rien n'est remboursé automatiquement** — c'est la parole de l'un contre celle
de l'autre, et un remboursement automatique serait une porte ouverte aux abus.
C'est vous qui tranchez, après avoir lu la messagerie de la commande. Pour
débloquer le vendeur : Django admin → *Commandes* → décochez
« Non-réception signalée », puis remettez une date de libération sur ses
écritures de portefeuille.

### Le client veut son argent, pas un avoir

Quand une commande est annulée, le client est recrédité **en avoir** :
utilisable tout de suite sur n'importe quelle commande. Sur sa page de
commande, il peut aussi demander à recevoir la somme **sur son mobile money**.

Cette demande arrive au même endroit que les retraits vendeurs, dans
*Retraits*, avec la mention **« ⟲ Remboursement client »**. Vous envoyez
l'argent à la main, puis vous marquez « versé » — le compte du client est
débité à ce moment-là, pas avant.

Pendant l'attente, la somme est **réservée** : le client ne peut pas la
dépenser en avoir et la recevoir en argent.

### Ce que la vérification vous dit

`python manage.py verifier_production` signale désormais :

- les clients qui déclarent ne pas avoir reçu leur commande (bloquant) ;
- les commandes confirmées mais **jamais marquées livrées** depuis plus de
  10 jours. Le plus souvent le vendeur a livré sans cliquer — relancez-le,
  sinon il ne sera jamais payé et vous garderez un argent qui n'est pas à vous.

---

## 6 quater. Sécurité des comptes

**Blocage automatique.** Après 5 mots de passe erronés en 15 minutes depuis
une même connexion, elle est bloquée 15 minutes. Rien à faire de votre part :
c'est ce qui arrête les robots qui essaient des milliers de mots de passe.

**Journal des connexions.** Django admin → *Journal des connexions* : chaque
tentative, réussie ou non, avec l'IP et l'heure. Si vous voyez une rafale
d'échecs sur votre propre compte, changez votre mot de passe et activez la
double authentification.

**Double authentification.** Chacun peut l'activer depuis son profil →
*Sécurité & connexion*. Un code à usage unique est alors demandé à chaque
connexion, par e-mail ou par SMS. Elle est **facultative** — beaucoup de vos
vendeurs n'ont pas d'e-mail — mais **activez-la sur votre propre compte
administrateur** : c'est lui qui donne accès à tout.

Pour l'activer sur votre compte : connectez-vous → Profil → Sécurité &
connexion → Activer. Vérifiez d'abord que votre e-mail est bien renseigné.

---

## 7. Sauvegarder vos données

**Faites-le avant chaque mise à jour.** En SQLite, la base tient dans un seul
fichier : copiez `db.sqlite3` et le dossier `media/` (les photos envoyées par les
utilisateurs) ailleurs que sur la machine.

Export lisible de toutes les données :

```bash
python manage.py dumpdata --indent 2 > sauvegarde.json
```

---

## 8. Rappels de sécurité

- Ne partagez jamais votre compte administrateur. Créez un second compte
  `is_staff` pour un collaborateur, sans cocher « superutilisateur ».
- En production : `DJANGO_DEBUG=False` dans le `.env`, sans exception. Avec
  `DEBUG=True`, la moindre erreur affiche votre configuration à l'écran.
- Le fichier `.env` contient vos clés : il ne doit jamais être envoyé sur GitHub
  (il est déjà dans le `.gitignore`).
- Les pièces d'identité et les contacts des livreurs ne sont visibles que par
  l'équipe. Ne les faites jamais circuler par WhatsApp.
