/* =========================================================
   EazyMarket — interactions de base (aucune dépendance)
   ========================================================= */
(function () {
  'use strict';

  /* ---- Menu mobile ---- */
  var toggle = document.querySelector('[data-nav-toggle]');
  var links = document.querySelector('[data-nav-links]');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---- Menus déroulants ---- */
  document.querySelectorAll('[data-dropdown]').forEach(function (dd) {
    var btn = dd.querySelector('[data-dropdown-btn]');
    if (!btn) return;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var wasOpen = dd.classList.contains('open');
      document.querySelectorAll('[data-dropdown].open').forEach(function (o) { o.classList.remove('open'); });
      if (!wasOpen) dd.classList.add('open');
    });
  });
  document.addEventListener('click', function () {
    document.querySelectorAll('[data-dropdown].open').forEach(function (o) { o.classList.remove('open'); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('[data-dropdown].open').forEach(function (o) { o.classList.remove('open'); });
    }
  });

  /* ---- Sélecteur de quantité ---- */
  document.querySelectorAll('[data-qty]').forEach(function (box) {
    var input = box.querySelector('input');
    box.querySelectorAll('[data-qty-step]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var step = parseInt(btn.getAttribute('data-qty-step'), 10);
        var max = parseInt(input.getAttribute('max') || '9999', 10);
        var val = (parseInt(input.value, 10) || 1) + step;
        input.value = Math.min(max, Math.max(1, val));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  });

  /* ---- Champs conditionnels du formulaire d'inscription ---- */
  var roleInputs = document.querySelectorAll('[data-role-input]');
  if (roleInputs.length) {
    var applyRole = function () {
      var checked = document.querySelector('[data-role-input]:checked');
      var role = checked ? checked.value : 'buyer';
      document.querySelectorAll('[data-role-block]').forEach(function (block) {
        var roles = block.getAttribute('data-role-block').split(',');
        block.classList.toggle('hidden', roles.indexOf(role) === -1);
      });
    };
    roleInputs.forEach(function (i) { i.addEventListener('change', applyRole); });
    applyRole();
  }

  /* ---- Masquage automatique des alertes ---- */
  document.querySelectorAll('.alert').forEach(function (a) {
    setTimeout(function () {
      a.style.transition = 'opacity 400ms, transform 400ms, max-height 400ms, margin 400ms, padding 400ms';
      a.style.opacity = '0';
      a.style.transform = 'translateY(-6px)';
      setTimeout(function () { a.remove(); }, 420);
    }, 7000);
  });

  /* ---- Copier dans le presse-papier ---- */
  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () {
          var old = btn.innerHTML;
          btn.innerHTML = '<i class="fas fa-check"></i> Copié';
          setTimeout(function () { btn.innerHTML = old; }, 1800);
        });
      }
    });
  });

  /* ---- Confirmation avant action destructrice ---- */
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!window.confirm(el.getAttribute('data-confirm'))) e.preventDefault();
    });
  });

  /* ---- Case à cocher qui révèle un bloc (ex : délai sur commande) ---- */
  document.querySelectorAll('[data-toggle-target]').forEach(function (box) {
    var cible = document.querySelector(box.getAttribute('data-toggle-target'));
    if (!cible) return;
    var maj = function () { cible.style.display = box.checked ? '' : 'none'; };
    maj();
    box.addEventListener('change', maj);
  });

  /* ---- Lecture d'une vidéo, uniquement à la demande ----
     Rien n'est téléchargé tant que le visiteur n'a pas cliqué : sur une
     connexion facturée au mégaoctet, une vidéo qui démarre seule coûte
     de l'argent au visiteur et le fait partir. */
  document.querySelectorAll('[data-video] .video-play').forEach(function (bouton) {
    bouton.addEventListener('click', function () {
      var cadre = bouton.closest('.video-cadre');
      var type = bouton.dataset.type;
      var src = bouton.dataset.src;
      if (!cadre || !src) return;

      if (type === 'lien') { window.open(src, '_blank', 'noopener'); return; }

      var lecteur;
      if (type === 'fichier') {
        lecteur = document.createElement('video');
        lecteur.src = src;
        lecteur.controls = true;
        lecteur.autoplay = true;
        lecteur.playsInline = true;
        lecteur.setAttribute('preload', 'auto');
      } else {
        lecteur = document.createElement('iframe');
        lecteur.src = src;
        lecteur.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture');
        lecteur.setAttribute('allowfullscreen', '');
        lecteur.setAttribute('loading', 'lazy');
        lecteur.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      }
      lecteur.className = 'video-lecteur';
      cadre.innerHTML = '';
      cadre.appendChild(lecteur);
    });
  });

  /* ---- Contrôle de la vidéo AVANT de l'envoyer ----
     Envoyer 15 Mo en 3G prend plusieurs minutes. Autant prévenir tout de
     suite que le fichier est trop long ou trop lourd, plutôt que de laisser
     le vendeur attendre pour rien et recommencer. */
  document.querySelectorAll('[data-video-form]').forEach(function (form) {
    var champ = form.querySelector('[data-video-input]');
    var erreur = form.querySelector('[data-video-erreur]');
    var envoyer = form.querySelector('[data-video-submit]');
    var maxS = parseInt(form.dataset.maxSeconds || '30', 10);
    var maxMo = parseInt(form.dataset.maxMo || '15', 10);

    form.querySelectorAll('[data-video-mode]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        form.querySelectorAll('[data-video-pan]').forEach(function (pan) {
          pan.hidden = pan.dataset.videoPan !== radio.value;
        });
      });
    });

    if (!champ) return;

    var afficher = function (message) {
      if (!erreur) return;
      erreur.textContent = message || '';
      erreur.hidden = !message;
      if (envoyer) envoyer.disabled = !!message;
    };

    champ.addEventListener('change', function () {
      afficher('');
      var fichier = champ.files && champ.files[0];
      if (!fichier) return;

      var mo = fichier.size / (1024 * 1024);
      if (mo > maxMo) {
        afficher('Cette vidéo pèse ' + mo.toFixed(0) + ' Mo, la limite est de ' +
                 maxMo + ' Mo. Filmez plus court, ou baissez la qualité dans ' +
                 'les réglages de votre appareil photo.');
        return;
      }

      var sonde = document.createElement('video');
      sonde.preload = 'metadata';
      sonde.onloadedmetadata = function () {
        URL.revokeObjectURL(sonde.src);
        if (sonde.duration && sonde.duration > maxS + 1) {
          afficher('Cette vidéo dure ' + Math.round(sonde.duration) +
                   ' secondes, la limite est de ' + maxS + '. Coupez-la avant de l\'envoyer.');
        }
      };
      sonde.onerror = function () { URL.revokeObjectURL(sonde.src); };
      sonde.src = URL.createObjectURL(fichier);
    });
  });

  /* ---- Nom du fichier choisi ----
     Le contrôle natif est masqué : sans ça, on ne saurait pas si le fichier
     a bien été pris en compte. */
  document.querySelectorAll('[data-fichier]').forEach(function (champ) {
    var etiquette = champ.parentNode.querySelector('[data-fichier-nom]');
    if (!etiquette) return;
    champ.addEventListener('change', function () {
      var f = champ.files && champ.files[0];
      etiquette.textContent = f ? f.name : '';
    });
  });

  /* ---- Compteur de notifications (rafraîchi toutes les 60 s) ---- */
  var dot = document.querySelector('[data-notif-count]');
  if (dot && dot.dataset.url) {
    setInterval(function () {
      fetch(dot.dataset.url, { headers: { 'x-requested-with': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.count > 0) { dot.textContent = d.count; dot.classList.remove('hidden'); }
          else { dot.classList.add('hidden'); }
        })
        .catch(function () {});
    }, 60000);
  }
})();
