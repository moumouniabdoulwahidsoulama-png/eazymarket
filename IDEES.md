# EazyMarket — idées pour se démarquer

Ce que la plupart des marketplaces africaines ne font pas, et qui est à votre
portée. Classé par rapport valeur / effort.

---

## Déjà implémenté dans cette version

**Le devis intégré.** C'est la différence de fond avec un simple annuaire. Le
client décrit, l'artisan chiffre par ligne (main-d'œuvre, fournitures,
déplacement, durée, validité), le client accepte ou refuse. Tout est écrit,
tracé, opposable. Les annuaires concurrents s'arrêtent au numéro de téléphone.

**La messagerie par demande.** Photos comprises. Les échanges restent attachés au
dossier — c'est ce qui vous permet d'arbitrer un litige au lieu de subir la
parole contre parole.

**Le portefeuille vendeur en écritures comptables.** Un solde n'est jamais un
champ modifiable : c'est la somme des mouvements. Auditable, infalsifiable.

**Le déblocage de contact à 200 F.** La fiche de l'artisan est entièrement
consultable, seul le numéro est masqué. Deux chemins : payer 200 F pour appeler
tout de suite, ou demander un devis gratuitement. Le premier contact de chaque
client est offert. C'est ce qui referme le trou par lequel la valeur s'échappait.

**Les emplacements d'annonces.** Le vendeur achète des emplacements définitifs
plutôt qu'un abonnement qui expire. Il comprend ce qu'il achète, et vous avez un
revenu d'entrée avant la première vente.

**Le prix arrondi.** La commission est ajoutée puis le total arrondi au palier
supérieur : jamais de 1 050 F à l'écran, et le vendeur touche exactement son
prix. Le calcul s'affiche en direct pendant qu'il saisit.

**Les icônes servies en local.** Aucun appel à un CDN : le site s'affiche
entièrement même avec une connexion coupée.

---

## À fort impact, effort raisonnable

### 1. WhatsApp comme canal principal, pas comme gadget

Vos utilisateurs vivent sur WhatsApp, pas dans leur boîte mail. Envoyez-y les
notifications importantes : devis reçu, commande expédiée, paiement confirmé.
Un lien `wa.me` existe déjà dans le pied de page ; l'étape suivante est l'API
WhatsApp Business (ou Twilio) branchée sur le modèle `Notification`.
**C'est le point qui augmentera le plus votre taux de réponse.**

### 2. Le mode « je ne sais pas qui appeler »

Aujourd'hui le client doit choisir un artisan. Beaucoup ne savent pas lequel.
Inversez : le client publie sa demande **sans destinataire**, elle part aux
artisans du métier et du quartier, et il reçoit 3 devis à comparer.

C'est le modèle qui a fait le succès des plateformes de travaux dans le monde,
et il double la valeur d'un abonnement Pro (accès aux demandes ouvertes).
Techniquement : rendre `artisan` optionnel sur `ServiceRequest` et ajouter une
liste « demandes ouvertes » dans l'espace artisan.

### 3. Fonctionner sans réseau ou presque

Ouagadougou n'a pas partout la 4G. Ajoutez un *service worker* et un manifeste :
le site devient installable comme une application, garde les pages consultées en
cache, et se relance instantanément. Peu de lignes de code, effet énorme sur la
perception de qualité.

### 4. La carte des artisans par quartier

Un plan simple (Leaflet + OpenStreetMap, gratuit) avec un point par artisan.
« Qui est près de chez moi » est la question numéro un, et une carte y répond
mieux qu'une liste. Ajoutez `latitude` / `longitude` au modèle `Artisan`.

### 5. Le paiement séquestré sur les gros chantiers

Pour un devis au-delà de 100 000 FCFA : le client verse à la plateforme,
l'argent est libéré à la validation des travaux. Vous prenez 3 % pour le
service — et vous réglez d'un coup le problème de confiance qui bloque les
chantiers importants. C'est la seule commission acceptable sur les services,
parce qu'elle achète une garantie réelle.
L'infrastructure (`Transaction`, `WalletEntry`) est déjà en place.

### 6. Le parrainage entre artisans

Un artisan qui en fait abonner trois gagne deux mois offerts. Vos meilleurs
recruteurs sont vos utilisateurs, et un menuisier connaît tous les menuisiers de
son quartier. Le mécanisme existe déjà pour les livreurs (`DeliveryReferral` +
`Sponsor`) — il ne demande qu'à être généralisé aux artisans.

### 6 bis. La remontée d'annonce à 200 F

Un vendeur dont le produit est descendu dans la liste paie 200 F pour le remettre
en tête pendant 3 jours. Montant indolore, effet visible immédiatement : c'est le
mécanisme qui rapporte le plus sur les sites de petites annonces. Le champ
`boosted_until` existe déjà sur `Product`.

### 6 ter. Le badge « Vérifié » à 2 000 F

Contrôle de la pièce d'identité, appel téléphonique, badge vert sur la fiche. Les
artisans sérieux veulent payer pour se distinguer — c'est l'inverse d'une taxe.
Paiement unique, marge quasi totale, et la plateforme s'assainit pendant que vous
êtes payé pour le faire. Le champ `is_verified` est déjà là.

---

## À plus long terme

### 7. La vérification d'identité comme produit

Le badge « Vérifié » vaut plus que n'importe quelle publicité sur un marché où
la confiance est rare. Faites-en un service payant assumé : 2 000 FCFA une fois,
avec contrôle de la pièce d'identité et appel téléphonique. Les artisans sérieux
paieront pour se distinguer des autres — et vous assainissez la plateforme en
étant payé pour le faire.

### 8. Le « fait au Burkina »

Un label et un filtre pour les produits fabriqués localement : karité, tissage,
bronze, cuir, maroquinerie, agroalimentaire. Distinctif, aligné sur un vrai
courant de consommation, et c'est l'angle qui rend le site racontable à la
presse et aux institutions.

### 9. Le catalogue partageable

Un bouton qui génère, pour chaque vendeur, une image ou un PDF de ses produits
prêt à envoyer sur WhatsApp. Chaque partage devient une porte d'entrée vers le
site. Faisable avec Pillow ou WeasyPrint, sans dépendance lourde.

### 10. Les achats groupés de quartier

Cinq voisins qui commandent le même sac de riz, une seule livraison, un prix
dégressif. Cela colle exactement aux habitudes d'achat, ça baisse votre coût
logistique et ça crée une raison de revenir chaque semaine.

### 11. Le tableau de bord vendeur qui conseille

Vous avez déjà les vues, les ventes et les stocks. Transformez-les en phrases
utiles : « votre produit X a été vu 40 fois sans être acheté — votre prix est
peut-être trop haut », « vous n'avez pas de photo sur 3 annonces ». C'est ce qui
transforme un tableau de bord en outil qu'on ouvre tous les jours.

---

## Ce qu'il ne faut pas faire tout de suite

- **Une application mobile native.** Un site rapide et installable couvre 95 %
  du besoin pour 5 % du coût. Repoussez.
- **S'étendre à une deuxième ville.** Gagnez d'abord Ouagadougou quartier par
  quartier. Une place de marché à moitié remplie dans deux villes vaut moins
  qu'une place de marché dense dans une seule.
- **Ouvrir tous les métiers d'un coup.** Trois métiers où vous avez dix bons
  artisans valent mieux que trente métiers avec un artisan chacun. Le client qui
  cherche et ne trouve personne ne revient pas.
