# EazyMarket — identité visuelle

## Le logo

Le logo est livré en SVG dans `static/img/` :

| Fichier | Usage |
|---|---|
| `logo.svg` | Logo complet (symbole + nom + baseline) — en-têtes, documents, réseaux |
| `logo-mark.svg` | Symbole seul — barre de navigation, avatar, application mobile |
| `logo-white.svg` | Version sur fond sombre — pied de page, affiches |
| `favicon.svg` | Onglet du navigateur |

Le SVG est vectoriel : il reste net d'une carte de visite à un panneau
publicitaire, et il pèse moins d'1 Ko.

### L'idée derrière le symbole

Un **panier de marché** (le commerce) qui contient une **étincelle à quatre
branches** en vert profond (le savoir-faire, l'artisan). Les deux moitiés de la
plateforme dans une seule forme, lisible à 16 pixels comme à 3 mètres.

L'orange évoque la latérite et le soleil de saison sèche — et, accessoirement,
la couleur du mobile money le plus utilisé du pays. Le vert profond apporte le
sérieux, la confiance, le contrat écrit.

### Les couleurs

| Rôle | Code | Où |
|---|---|---|
| Orange marque | `#EE6C2B` | Boutons principaux, liens, accents |
| Orange clair | `#F79420` | Dégradés |
| Orange foncé | `#D9481F` | Survol, dégradés |
| Vert profond | `#0F4534` | Pied de page, services, confiance |
| Vert moyen | `#17694F` | Dégradés du bandeau d'accueil |
| Or | `#F2B705` | Étoiles, badges, mises en avant |
| Encre | `#101A16` | Titres et texte |
| Sable | `#FBF8F4` | Fond de page |

Toutes ces valeurs vivent dans `static/css/tokens.css`. **Changer la couleur de
marque du site entier = modifier `--brand-500`.**

### Les polices

- **Outfit** (700/800) pour les titres et le nom de marque — géométrique, chaude,
  très lisible sur petit écran.
- **Inter** (400/600) pour le texte courant.

Toutes deux gratuites sur Google Fonts, déjà chargées dans `templates/base.html`.

### Règles d'usage

- Laissez toujours autour du logo un espace vide égal à la hauteur du symbole.
- Ne changez ni les couleurs, ni les proportions, ni l'inclinaison.
- Sur photo ou fond coloré : `logo-white.svg`.
- Taille minimale du symbole : 24 px. En dessous, utilisez `favicon.svg`.

---

## Prompts pour régénérer ou faire varier le logo

À utiliser avec Midjourney, DALL·E, Ideogram, Recraft ou Adobe Firefly. Ideogram
et Recraft sont les meilleurs pour le texte et le vectoriel.

### Prompt principal (symbole seul)

> Minimalist flat vector logo mark for "EazyMarket", a West African online
> marketplace. A simple rounded shopping bag silhouette in white, containing a
> four-pointed sparkle in deep forest green. The bag sits inside a rounded square
> badge with a warm gradient from golden orange (#F79420) to burnt orange
> (#D9481F). Geometric, clean, thick shapes, no outlines, no gradients inside the
> bag, no text. Designed to stay legible at 16 pixels. Flat design, solid
> background, centered, generous padding. Modern African fintech aesthetic.

### Prompt avec le nom

> Modern logo lockup for "EazyMarket". Left: a rounded square badge with an
> orange gradient containing a white shopping bag with a deep green four-pointed
> sparkle. Right: the wordmark "EazyMarket" in a bold geometric sans-serif,
> "Eazy" in near-black and "Market" in orange, with a small uppercase tagline
> "BOUTIQUE · SERVICES" underneath in grey, widely letter-spaced. Clean, flat,
> professional, white background, horizontal layout.

### Variante « double métier » (plus audacieuse)

> Flat vector logo mark: a shopping bag whose two handles are different — the
> left handle is a normal rounded arc, the right handle is the open jaw of a
> wrench. Two ideas in one shape: commerce and craftsmanship. White on a warm
> orange gradient rounded square. Extremely simple, thick strokes, no text,
> readable at very small size.

### Pour l'application mobile

> App icon, 1024x1024, rounded square, warm orange gradient background, centered
> white shopping bag glyph with a deep green sparkle inside, generous margins,
> no text, flat design, iOS style.

### À exiger dans tous les cas

- **format SVG ou vectoriel** — un PNG flou tue une marque ;
- **aucun texte généré par l'IA** dans le symbole (les modèles écrivent mal) —
  le nom s'ajoute ensuite avec la vraie police ;
- une version **monochrome noire** et une **monochrome blanche**, pour le
  tampon, la sérigraphie et les documents en noir et blanc.

---

## Décliner l'identité ailleurs

- **Bannière Facebook / WhatsApp Business** : fond dégradé vert profond, logo
  blanc à gauche, phrase « Achetez. Trouvez un pro. Au même endroit. » à droite.
- **Sticker moto pour les livreurs** : symbole seul sur fond orange, numéro
  WhatsApp en dessous. C'est votre affichage le moins cher et le plus vu.
- **Reçu papier / facture** : `logo.svg` en haut à gauche, tout le reste en noir.
- **Photos produits** : fond neutre uni, lumière du jour, aucun filtre. Une
  fiche produit avec une vraie photo se vend nettement mieux qu'une fiche sans.
