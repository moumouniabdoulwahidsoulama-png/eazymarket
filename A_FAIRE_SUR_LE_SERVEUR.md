# Mise à jour du site — marche à suivre

> ## ⚠ Si la vérification vous dit « base non-MySQL » ou « sqlite3 »
>
> **Votre fichier `.env` manque.** Vos données ne sont pas perdues : votre
> base MySQL est intacte, l'application ne la trouve simplement plus et s'est
> rabattue sur une base vide.
>
> Ne relancez rien, ne recréez pas de compte administrateur. Allez directement
> à la section **« Le fichier .env a disparu »**, tout en bas de ce document.


Cette version apporte **deux choses** : la confirmation du vendeur sous 24 h
(l'argent du client est protégé) et les **vidéos** sur les produits et les
profils d'artisans.

Fichier à envoyer : **`eazymarket-a-envoyer.zip`**, dans ce dossier.

Comptez 20 minutes. Faites-le à une heure creuse : le site sera indisponible
une ou deux minutes.

---

## 1. Sauvegarder d'abord (5 min, non négociable)

Si quelque chose se passe mal, c'est ce qui vous sauve.

1. cPanel → **phpMyAdmin** → sélectionnez votre base → onglet **Exporter** →
   *Exécuter*. Un fichier `.sql` est téléchargé : gardez-le.
2. cPanel → **Gestionnaire de fichiers** → clic droit sur le dossier
   `eazymarket` → **Compresser** → gardez l'archive.

---

## 2. Envoyer la nouvelle version (3 min)

1. cPanel → **Gestionnaire de fichiers** → entrez dans le dossier `eazymarket`.
2. Bouton **Téléverser** → choisissez `eazymarket-a-envoyer.zip`.
3. Revenez au dossier, clic droit sur le ZIP → **Extraire** → destination :
   le dossier `eazymarket` lui-même.
4. À la question « écraser les fichiers existants ? » → **Oui, tout écraser**.
5. Supprimez le ZIP du serveur une fois l'extraction terminée.

> Votre `.env`, votre base de données et les photos déjà envoyées ne sont pas
> dans le ZIP : ils ne sont pas touchés.

---

## 3. Relever les limites d'envoi, pour les vidéos (2 min)

Sans ce réglage, un vendeur qui envoie une vidéo verra l'envoi échouer.

cPanel → **Sélectionner la version de PHP** (ou *MultiPHP INI Editor*) →
onglet **Options** :

| Réglage | Valeur |
|---|---|
| `upload_max_filesize` | `20M` |
| `post_max_size` | `25M` |
| `max_execution_time` | `120` |
| `memory_limit` | `256M` |

Enregistrez.

---

## 4. Lancer la mise à jour (3 min)

cPanel → **Terminal** (ou Setup Python App → *Execute python script*) :

```bash
source /home/VOTRE-UTILISATEUR/virtualenv/eazymarket/3.11/bin/activate
cd /home/VOTRE-UTILISATEUR/eazymarket
python deploiement/mise_en_ligne.py
```

Remplacez `VOTRE-UTILISATEUR` par votre nom d'utilisateur cPanel
(celui qui apparaît dans les chemins du Gestionnaire de fichiers).

La commande fait tout, dans l'ordre : migrations de la base, encodage,
catalogue, fichiers statiques, protection des dossiers, puis une vérification
qui affiche ce qui va et ce qui ne va pas.

**Ce que vous devez voir à la fin :** `Aucun problème bloquant.`
Si une ligne `[ERREUR]` apparaît, corrigez-la avant de continuer — le message
dit quoi faire.

---

## 5. Redémarrer l'application (30 s)

cPanel → **Setup Python App** → votre application → bouton **RESTART**.

Sans ce redémarrage, le site continue de tourner sur l'ancien code.

---

## 6. Ajouter la tâche automatique horaire (2 min)

**C'est la plus importante de toutes.** C'est elle qui rembourse un client
quand le vendeur n'a pas répondu dans les 24 h. Sans elle, l'argent d'un
client reste bloqué indéfiniment.

cPanel → **Tâches Cron** → *Ajouter une nouvelle tâche cron*
→ Réglage courant : **Deux fois par heure** ou saisissez `0 * * * *`.

Commande :

```bash
/home/VOTRE-UTILISATEUR/virtualenv/eazymarket/3.11/bin/python /home/VOTRE-UTILISATEUR/eazymarket/manage.py traiter_commandes >> /home/VOTRE-UTILISATEUR/eazymarket/logs/cron.log 2>&1
```

Vous devez avoir **deux** tâches cron au total :

| Quand | Commande | À quoi ça sert |
|---|---|---|
| `0 * * * *` (chaque heure) | `traiter_commandes` | Rembourse les clients non servis |
| `0 2 * * *` (chaque nuit) | `liberer_gains` | Rend les gains retirables |

---

## 7. Vérifier que tout marche (5 min)

Sur votre téléphone, sur le site en ligne :

1. **La vidéo.** Connectez-vous avec votre compte → *Ma boutique* → ouvrez le
   crayon d'une annonce → un bloc **Vidéos** apparaît en bas. Essayez d'abord
   l'onglet **Coller un lien** avec une adresse TikTok ou YouTube : c'est
   instantané et ça ne consomme rien. Puis ouvrez la fiche du produit : la
   vignette doit s'afficher, et la vidéo ne doit démarrer **qu'au clic**.
2. **L'envoi de fichier.** Filmez 10 secondes avec votre téléphone et envoyez
   la vidéo. Si l'envoi échoue, c'est l'étape 3 qui n'est pas passée.
3. **La confirmation.** Passez une petite commande depuis un autre compte.
   Votre compte vendeur doit voir « À confirmer maintenant » avec le compte à
   rebours, et le client doit lire « Votre paiement est protégé ».

---

## Si quelque chose casse

Le site affiche une erreur 500 :

1. cPanel → Gestionnaire de fichiers → `eazymarket/logs/` → ouvrez le journal
   le plus récent, la dernière ligne dit ce qui manque.
2. Le plus souvent : l'étape 4 n'a pas été lancée, ou l'application n'a pas
   été redémarrée (étape 5).

Pour revenir en arrière : réextrayez l'archive du dossier faite à l'étape 1,
puis réimportez le `.sql` dans phpMyAdmin.

---

## Deux choses encore en attente, depuis l'autre fois

- **Changer le mot de passe de la base** et **celui de la boîte mail** :
  vous me les avez envoyés en clair dans la conversation. cPanel →
  *Bases de données MySQL* et *Comptes de messagerie*, puis reportez les
  nouveaux dans le `.env`.
- **La passerelle SMS**, quand vous en aurez une. En attendant, relancez les
  vendeurs depuis votre tableau de bord administrateur : le bouton
  « Relancer » ouvre WhatsApp avec le message déjà écrit.

---

## Le fichier .env a disparu — comment réparer

**Symptômes.** La vérification affiche `base non-MySQL : rien à faire`, ou
`Connexion établie (sqlite3)`, ou encore `12 pays (12 nouveaux)` alors que
votre site tournait déjà. Le site paraît vide, ou répond `Bad Request (400)`.

**Ce qui s'est passé.** Le fichier `.env`, qui contient l'adresse de votre
base de données et vos mots de passe, n'est plus à la racine de
l'application. Sans lui, Django repart sur ses réglages d'usine : une base
SQLite neuve et vide.

**Ce qui n'a PAS été perdu.** Votre base MySQL, avec tous vos comptes, vos
produits et vos commandes. Elle n'a pas été touchée : l'application ne
l'ouvre simplement plus.

### Étape 0 — Demander à l'application ce qu'elle a lu

```bash
cd /home/VOTRE-UTILISATEUR/eazymarket
python manage.py verifier_env
```

Cette commande liste les réglages que l'application a réellement lus dans
votre `.env`, ceux qui manquent, et les lignes qu'elle n'a pas comprises.
**Aucun mot de passe n'est affiché.** Elle finit en disant quelle base de
données est vraiment utilisée : c'est la réponse à la question.

Un `.env` peut exister et n'être lu qu'à moitié. Les causes fréquentes,
toutes signalées par cette commande :

| Dans le fichier | Ce qui se passe |
|---|---|
| `DB NAME=...` (espace au lieu de `_`) | la ligne est ignorée |
| `**DB_NAME**=...` (recopié depuis une discussion) | les `*` sont retirés, mais vérifiez |
| `DB_NAME` sans `=` | la ligne est ignorée |
| La même clé écrite deux fois | seule la **première** compte |
| Fichier enregistré par le Bloc-notes Windows | marque invisible en tête |

### Étape 1 — Vérifier que le fichier est là

cPanel → **Terminal** :

```bash
ls -la /home/VOTRE-UTILISATEUR/eazymarket/.env
```

- `No such file` → le fichier manque, continuez.
- Le fichier existe → vous n'êtes pas dans le bon dossier ; comparez avec le
  chemin affiché par la vérification.

> Dans le Gestionnaire de fichiers, un nom commençant par un point est
> **caché par défaut**. Réglages (en haut à droite) → cochez
> *Afficher les fichiers cachés (dotfiles)*.

### Étape 2 — Supprimer la base vide créée par erreur

```bash
cd /home/VOTRE-UTILISATEUR/eazymarket
rm -f db.sqlite3
```

Sans ça, elle resterait là à occuper de la place et à semer la confusion.

### Étape 3 — Remettre le .env

**Si vous en avez gardé une copie** (sur votre ordinateur, ou le fichier
`.env.sauvegarde` sur le serveur) : reposez-la à la racine de l'application,
sous le nom exact `.env`, puis :

```bash
chmod 600 /home/VOTRE-UTILISATEUR/eazymarket/.env
```

**Si vous ne l'avez plus** :

```bash
cd /home/VOTRE-UTILISATEUR/eazymarket
python deploiement/configurer.py
```

Le script pose cinq questions et écrit le fichier. **Le point vital : à la
question sur la base de données, indiquez EXACTEMENT le même nom, le même
utilisateur et le même mot de passe qu'avant.** Vous les retrouvez dans
cPanel → *Bases de données MySQL*. Si vous vous trompez, le site repart à
vide — et cette fois pour de bon.

### Étape 4 — Relancer

```bash
python deploiement/mise_en_ligne.py
```

La vérification doit maintenant afficher `Connexion établie (mysql)` et
`0 nouveaux` pour les pays et les rayons. C'est la preuve que vous êtes bien
revenu sur votre vraie base.

### Étape 5 — Redémarrer

cPanel → **Setup Python App** → **RESTART**.

### Pour que ça ne se reproduise plus

Depuis cette version, l'application **refuse de démarrer** sans son `.env`
au lieu de se rabattre en silence sur une base vide, et
`mise_en_ligne.py` s'arrête avant la moindre migration. Vous verrez un
message clair au lieu d'un site mystérieusement vide.

Gardez malgré tout une copie de votre `.env` sur votre ordinateur, dans un
endroit que vous n'effacez pas. Ce fichier ne se retrouve nulle part
ailleurs : il contient des mots de passe qui n'existent qu'à cet endroit.
