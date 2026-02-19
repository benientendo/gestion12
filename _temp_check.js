
// === DONNÉES DJANGO ===

var FACT_FOURNISSEURS = [
    
    { id: 3, nom: "MARSARCO" },
    
    { id: 2, nom: "chinoi" },
    
    { id: 1, nom: "congo future" },
    
    { id: 4, nom: "kiyambu" },
    
];
var FACT_CATEGORIES = [
    
];
var FACT_ARTICLES = [
    
    { id: 123, nom: "", code: "ART\u002DA82E4432", prix_vente: 3500.00, prix_achat: 2500.00, devise: "CDF", stock: 45, categorie_id: "" },
    
    { id: 126, nom: "", code: "ART\u002D31B667DB", prix_vente: 0, prix_achat: 0, devise: "CDF", stock: 1, categorie_id: "" },
    
    { id: 127, nom: "", code: "ART\u002D4FB1E71B", prix_vente: 0, prix_achat: 0, devise: "CDF", stock: 1, categorie_id: "" },
    
    { id: 128, nom: "", code: "ART\u002D766102E3", prix_vente: 0, prix_achat: 0, devise: "CDF", stock: 1, categorie_id: "" },
    
    { id: 129, nom: "", code: "ART\u002DA463A8EC", prix_vente: 0, prix_achat: 0, devise: "CDF", stock: 1, categorie_id: "" },
    
    { id: 119, nom: "SARDINNE", code: "ART\u002DFC7CF1F4", prix_vente: 3000.00, prix_achat: 2000.00, devise: "CDF", stock: 250, categorie_id: "" },
    
    { id: 120, nom: "TOMATE", code: "ART\u002D1E0F9183", prix_vente: 700.00, prix_achat: 600.00, devise: "CDF", stock: 90, categorie_id: "" },
    
    { id: 37, nom: "allumette", code: "1\u002D003", prix_vente: 20000.00, prix_achat: 10000.00, devise: "CDF", stock: 220, categorie_id: "" },
    
    { id: 84, nom: "bleuband", code: "9873", prix_vente: 0, prix_achat: 766.67, devise: "CDF", stock: 620, categorie_id: "" },
    
    { id: 85, nom: "chaise", code: "12\u002D9FBAD4C3", prix_vente: 100.00, prix_achat: 80.00, devise: "USD", stock: 0, categorie_id: "" },
    
    { id: 51, nom: "chargeur oremo", code: "2223333", prix_vente: 50000.00, prix_achat: 70000.00, devise: "CDF", stock: 25, categorie_id: "" },
    
    { id: 47, nom: "chemise", code: "ART\u002D7AF27CAA", prix_vente: 10.00, prix_achat: 15.00, devise: "CDF", stock: 100, categorie_id: "" },
    
    { id: 125, nom: "dddff", code: "jhhhh", prix_vente: 11500000.00, prix_achat: 7666.67, devise: "CDF", stock: 65, categorie_id: "" },
    
    { id: 76, nom: "fufu", code: "8562", prix_vente: 450.00, prix_achat: 0, devise: "CDF", stock: 60, categorie_id: "" },
    
    { id: 52, nom: "huawei", code: "12\u002DD8DAFA75", prix_vente: 40000.00, prix_achat: 0, devise: "CDF", stock: 5, categorie_id: "" },
    
    { id: 81, nom: "huile", code: "2543", prix_vente: 75600.00, prix_achat: 50000.00, devise: "CDF", stock: 30, categorie_id: "" },
    
    { id: 124, nom: "huile vegetal", code: "ART\u002DB501E0CD", prix_vente: 46000000.00, prix_achat: 17250.00, devise: "CDF", stock: 23, categorie_id: "" },
    
    { id: 53, nom: "iphone12pro", code: "004545", prix_vente: 45.00, prix_achat: 31.50, devise: "CDF", stock: 15, categorie_id: "" },
    
    { id: 48, nom: "iphone_12pro", code: "ART\u002D36F5C1B5", prix_vente: 15.00, prix_achat: 10.00, devise: "USD", stock: 0, categorie_id: "" },
    
    { id: 54, nom: "ivory", code: "005", prix_vente: 12000.00, prix_achat: 10000.00, devise: "CDF", stock: 0, categorie_id: "14" },
    
    { id: 78, nom: "jus", code: "3698", prix_vente: 9000.00, prix_achat: 7500.00, devise: "CDF", stock: 258, categorie_id: "" },
    
    { id: 74, nom: "loso", code: "4589", prix_vente: 48000.00, prix_achat: 35000.00, devise: "CDF", stock: 892, categorie_id: "" },
    
    { id: 73, nom: "madesu", code: "4568", prix_vente: 9850.00, prix_achat: 8000.00, devise: "CDF", stock: 0, categorie_id: "" },
    
    { id: 75, nom: "makayabu", code: "78562", prix_vente: 123500.00, prix_achat: 90000.00, devise: "CDF", stock: 460, categorie_id: "" },
    
    { id: 122, nom: "mayo", code: "ART\u002D5B9D1701", prix_vente: 0, prix_achat: 4600.00, devise: "CDF", stock: 35, categorie_id: "" },
    
    { id: 43, nom: "orange", code: "ART\u002D4C9D71E8", prix_vente: 9.00, prix_achat: 5.00, devise: "USD", stock: 0, categorie_id: "" },
    
    { id: 55, nom: "papier thermique", code: "12\u002D7F4C4276", prix_vente: 7000.00, prix_achat: 5000.00, devise: "CDF", stock: 0, categorie_id: "" },
    
    { id: 56, nom: "redmi4", code: "12\u002D6D507BB2", prix_vente: 50000.00, prix_achat: 0, devise: "CDF", stock: 0, categorie_id: "" },
    
    { id: 45, nom: "sac fille", code: "ART\u002D102D7537", prix_vente: 80.00, prix_achat: 60.00, devise: "USD", stock: 10, categorie_id: "" },
    
    { id: 72, nom: "safuti", code: "1256", prix_vente: 7500.00, prix_achat: 6000.00, devise: "CDF", stock: 120, categorie_id: "" },
    
    { id: 83, nom: "sardine", code: "6984", prix_vente: 86500.00, prix_achat: 75000.00, devise: "CDF", stock: 52, categorie_id: "" },
    
    { id: 57, nom: "savon noir", code: "0030", prix_vente: 5000.00, prix_achat: 3500.00, devise: "CDF", stock: 0, categorie_id: "13" },
    
    { id: 71, nom: "savon rouge", code: "1234", prix_vente: 15600.00, prix_achat: 8000.00, devise: "CDF", stock: 80, categorie_id: "" },
    
    { id: 79, nom: "soso", code: "6595", prix_vente: 120000.00, prix_achat: 60000.00, devise: "CDF", stock: 26, categorie_id: "" },
    
    { id: 82, nom: "spaguetti", code: "2698", prix_vente: 1200.00, prix_achat: 600.00, devise: "CDF", stock: 56, categorie_id: "" },
    
    { id: 41, nom: "tomate", code: "ART\u002D97F804DD", prix_vente: 10000.00, prix_achat: 5000.00, devise: "CDF", stock: 100, categorie_id: "" },
    
    { id: 86, nom: "velo", code: "12\u002D171F0977", prix_vente: 50.00, prix_achat: 40.00, devise: "CDF", stock: 0, categorie_id: "" },
    
    { id: 80, nom: "viande", code: "6963", prix_vente: 135000.00, prix_achat: 120000.00, devise: "CDF", stock: 0, categorie_id: "" },
    
    { id: 77, nom: "vinaigne", code: "89652", prix_vente: 6000.00, prix_achat: 3500.00, devise: "CDF", stock: 25, categorie_id: "" },
    
    { id: 58, nom: "yyyy", code: "12\u002D6B3A5877", prix_vente: 50.00, prix_achat: 0, devise: "CDF", stock: 0, categorie_id: "" },
    
];


// Dernières données d'approvisionnement par article (carton, prix, etc.)
var FACT_DERNIERS_APPROS = {"76": {"type_quantite": "CARTON", "nombre_cartons": 0, "pieces_par_carton": 1, "prix_achat_carton": 0.0, "prix_achat_unitaire": 0.0}, "84": {"type_quantite": "CARTON", "nombre_cartons": 2, "pieces_par_carton": 300, "prix_achat_carton": 230000.0, "prix_achat_unitaire": 766.67}, "119": {"type_quantite": "CARTON", "nombre_cartons": 3, "pieces_par_carton": 50, "prix_achat_carton": 100000.0, "prix_achat_unitaire": 2000.0}, "120": {"type_quantite": "CARTON", "nombre_cartons": 2, "pieces_par_carton": 50, "prix_achat_carton": 30000.0, "prix_achat_unitaire": 600.0}, "122": {"type_quantite": "CARTON", "nombre_cartons": 1, "pieces_par_carton": 30, "prix_achat_carton": 138000.0, "prix_achat_unitaire": 4600.0}, "123": {"type_quantite": "CARTON", "nombre_cartons": 2, "pieces_par_carton": 20, "prix_achat_carton": 50000.0, "prix_achat_unitaire": 2500.0}, "124": {"type_quantite": "CARTON", "nombre_cartons": 1, "pieces_par_carton": 20, "prix_achat_carton": 345000.0, "prix_achat_unitaire": 17250.0}, "125": {"type_quantite": "CARTON", "nombre_cartons": 2, "pieces_par_carton": 30, "prix_achat_carton": 230000.0, "prix_achat_unitaire": 7666.67}, "126": {"type_quantite": "UNITE", "nombre_cartons": 0, "pieces_par_carton": 1, "prix_achat_carton": 0.0, "prix_achat_unitaire": 0.0}, "127": {"type_quantite": "UNITE", "nombre_cartons": 0, "pieces_par_carton": 1, "prix_achat_carton": 0.0, "prix_achat_unitaire": 0.0}, "128": {"type_quantite": "UNITE", "nombre_cartons": 0, "pieces_par_carton": 1, "prix_achat_carton": 0.0, "prix_achat_unitaire": 0.0}, "129": {"type_quantite": "UNITE", "nombre_cartons": 0, "pieces_par_carton": 1, "prix_achat_carton": 0.0, "prix_achat_unitaire": 0.0}};

// === ÉTAT ===
var factArticlesAjoutes = [];
var FACT_STORAGE_KEY = 'facture_brouillon_13';

// === PERSISTANCE localStorage ===
function factSaveState() {
    try {
        var state = {
            articles: factArticlesAjoutes,
            header: {
                numero_facture: getEl('numero_facture').value,
                date_facture: getEl('date_facture').value,
                devise: getEl('devise').value,
                fournisseur_input: getEl('fournisseur_input').value,
                fournisseur_id: getEl('fournisseur_id').value,
                fournisseur_nom: getEl('fournisseur_nom').value,
                notes: document.querySelector('input[name="notes"]').value
            },
            savedAt: new Date().toISOString()
        };
        localStorage.setItem(FACT_STORAGE_KEY, JSON.stringify(state));
        // Indicateur visuel
        var ind = getEl('saveIndicator');
        if (ind) {
            ind.style.display = 'inline';
            ind.textContent = '\u2713 Brouillon sauvegardé (' + factArticlesAjoutes.length + ' art.)';
            clearTimeout(window._saveTimer);
            window._saveTimer = setTimeout(function() { ind.style.display = 'none'; }, 3000);
        }
        console.log('\ud83d\udcbe Sauvegardé:', factArticlesAjoutes.length, 'articles');
    } catch(err) { console.warn('Save state error:', err); }
}

// Sauvegarder automatiquement avant de quitter la page
window.addEventListener('beforeunload', function() {
    if (factArticlesAjoutes.length > 0) factSaveState();
});

function factLoadState() {
    try {
        var raw = localStorage.getItem(FACT_STORAGE_KEY);
        if (!raw) return false;
        var state = JSON.parse(raw);
        if (!state || !state.articles || state.articles.length === 0) {
            // Restaurer seulement l'en-tête s'il y a des données
            if (state && state.header) {
                var h = state.header;
                if (h.numero_facture) getEl('numero_facture').value = h.numero_facture;
                if (h.date_facture) getEl('date_facture').value = h.date_facture;
                if (h.devise) getEl('devise').value = h.devise;
                if (h.fournisseur_input) {
                    getEl('fournisseur_input').value = h.fournisseur_input;
                    if (h.fournisseur_id) {
                        getEl('fournisseur_id').value = h.fournisseur_id;
                        getEl('fournisseur_input').classList.add('input-matched');
                    }
                    if (h.fournisseur_nom) getEl('fournisseur_nom').value = h.fournisseur_nom;
                }
                if (h.notes) document.querySelector('input[name="notes"]').value = h.notes;
            }
            return false;
        }
        // Restaurer les articles
        factArticlesAjoutes = state.articles;
        // Restaurer l'en-tête
        if (state.header) {
            var h = state.header;
            if (h.numero_facture) getEl('numero_facture').value = h.numero_facture;
            if (h.date_facture) getEl('date_facture').value = h.date_facture;
            if (h.devise) {
                getEl('devise').value = h.devise;
                getEl('info_conversion').style.display = h.devise === 'USD' ? 'block' : 'none';
            }
            if (h.fournisseur_input) {
                getEl('fournisseur_input').value = h.fournisseur_input;
                if (h.fournisseur_id) {
                    getEl('fournisseur_id').value = h.fournisseur_id;
                    getEl('fournisseur_input').classList.add('input-matched');
                }
                if (h.fournisseur_nom) getEl('fournisseur_nom').value = h.fournisseur_nom;
            }
            if (h.notes) document.querySelector('input[name="notes"]').value = h.notes;
        }
        factRafraichirTableau();
        factMajResume();
        var savedAt = state.savedAt ? new Date(state.savedAt) : null;
        var timeStr = savedAt ? savedAt.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'}) : '';
        console.log('\ud83d\udccb Brouillon restaur\u00e9: ' + factArticlesAjoutes.length + ' articles' + (timeStr ? ' (sauvegard\u00e9 \u00e0 ' + timeStr + ')' : ''));
        // Indicateur visuel de restauration
        var ind = getEl('saveIndicator');
        if (ind) {
            ind.style.display = 'inline';
            ind.style.color = '#0d6efd';
            ind.textContent = '\ud83d\udccb Restaur\u00e9: ' + factArticlesAjoutes.length + ' articles' + (timeStr ? ' (sauvegard\u00e9 \u00e0 ' + timeStr + ')' : '');
            setTimeout(function() { ind.style.display = 'none'; ind.style.color = '#198754'; }, 5000);
        }
        return true;
    } catch(err) { console.warn('Load state error:', err); return false; }
}

function factClearState() {
    try { localStorage.removeItem(FACT_STORAGE_KEY); } catch(err) {}
}

// === HELPER ===
function getEl(id) { return document.getElementById(id); }
function factFormatNumber(n) { return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n); }
function factGetTaux() { return parseFloat(getEl('taux_dollar').value) || 2800; }
function factEscapeHtml(str) { var d = document.createElement('div'); d.textContent = str; return d.innerHTML; }

// === ARTICLE SÉLECTIONNÉ (pour hints) ===
var factSelectedArticle = null;

function showHint(hintId, value, devise) {
    var el = getEl(hintId);
    if (!el) return;
    var span = el.querySelector('.hint-val');
    if (span) span.textContent = factFormatNumber(value) + (devise ? ' ' + devise : '');
    el.classList.add('visible');
    el.dataset.hintValue = value;
}

function hideAllHints() {
    var hints = document.querySelectorAll('.hint-prev');
    for (var i = 0; i < hints.length; i++) {
        hints[i].classList.remove('visible');
        hints[i].dataset.hintValue = '';
    }
    factSelectedArticle = null;
}

function applyHint(fieldId, hintEl) {
    var val = hintEl.dataset.hintValue;
    if (val !== undefined && val !== '') {
        getEl(fieldId).value = val;
        calculerSaisie();
    }
}

// =============================================
// NAVIGATION ENTER
// =============================================
function factGetVisibleFields() {
    var type = getEl('art_type').value;
    var all = document.querySelectorAll('.nav-field, .art-field');
    var result = [];
    for (var i = 0; i < all.length; i++) {
        var f = all[i];
        if (f.offsetParent === null) continue;
        if (type === 'CARTON' && f.closest('.champs-saisie-unite')) continue;
        if (type !== 'CARTON' && f.closest('.carton-fields')) continue;
        result.push(f);
    }
    return result;
}

document.addEventListener('keydown', function(e) {
    try {
        if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
            e.preventDefault();
            getEl('factureForm').requestSubmit();
            return;
        }
        if (e.key !== 'Enter') return;
        var el = document.activeElement;
        if (!el) return;
        if (el.tagName === 'BUTTON' || el.type === 'submit') return;
        e.preventDefault();

        var fields = factGetVisibleFields();
        var idx = -1;
        for (var i = 0; i < fields.length; i++) {
            if (fields[i] === el) { idx = i; break; }
        }
        if (idx < 0) return;

        if (idx === fields.length - 1 && el.classList.contains('art-field')) {
            ajouterArticle();
            return;
        }
        if (idx < fields.length - 1) {
            fields[idx + 1].focus();
            if (fields[idx + 1].select) fields[idx + 1].select();
        }
    } catch(err) { console.error('Enter nav error:', err); }
});

// =============================================
// AUTOCOMPLETE ARTICLE
// =============================================
function onSaisieArticleInput() {
    try {
        var input = getEl('art_nom');
        var val = input.value.trim();
        var match = null;
        for (var i = 0; i < FACT_ARTICLES.length; i++) {
            if (FACT_ARTICLES[i].nom.toLowerCase() === val.toLowerCase()) { match = FACT_ARTICLES[i]; break; }
        }
        if (match) {
            factSelectedArticle = match;
            getEl('art_id').value = match.id;
            getEl('art_code').value = match.code;
            input.classList.add('input-matched');

            // Catégorie
            if (match.categorie_id) {
                for (var j = 0; j < FACT_CATEGORIES.length; j++) {
                    if (String(FACT_CATEGORIES[j].id) === String(match.categorie_id)) {
                        getEl('art_categorie').value = FACT_CATEGORIES[j].nom;
                        getEl('art_categorie_id').value = FACT_CATEGORIES[j].id;
                        getEl('art_categorie_nom').value = '';
                        getEl('art_categorie').classList.add('input-matched');
                        break;
                    }
                }
            }

            var dev = match.devise || 'CDF';
            var appro = FACT_DERNIERS_APPROS[String(match.id)];

            // Si dernière facture était en carton, basculer automatiquement
            if (appro && appro.type_quantite === 'CARTON') {
                getEl('art_type').value = 'CARTON';
                onSaisieTypeChange(true);
                // Pré-remplir champs carton
                if (appro.nombre_cartons > 0) {
                    getEl('art_nb_cartons').value = appro.nombre_cartons;
                    showHint('hint_nb_cartons', appro.nombre_cartons, 'crt');
                }
                if (appro.pieces_par_carton > 0) {
                    getEl('art_pcs_carton').value = appro.pieces_par_carton;
                    showHint('hint_pcs_carton', appro.pieces_par_carton, 'pcs');
                }
                if (appro.prix_achat_carton > 0) {
                    getEl('art_prix_carton').value = appro.prix_achat_carton;
                    showHint('hint_prix_carton', appro.prix_achat_carton, dev);
                }
            }

            // Pré-remplir prix d'achat + hint
            if (appro && appro.prix_achat_unitaire > 0) {
                getEl('art_prix_achat').value = appro.prix_achat_unitaire;
                showHint('hint_prix_achat', appro.prix_achat_unitaire, dev);
            } else if (match.prix_achat > 0) {
                getEl('art_prix_achat').value = match.prix_achat;
                showHint('hint_prix_achat', match.prix_achat, dev);
            }

            // Pré-remplir prix de vente + hint
            if (match.prix_vente > 0) {
                getEl('art_prix_vente').value = match.prix_vente;
                getEl('art_prix_vente_carton').value = match.prix_vente;
                showHint('hint_prix_vente', match.prix_vente, dev);
                showHint('hint_prix_vente_carton', match.prix_vente, dev);
            }

            // Hint stock actuel
            showHint('hint_qte', match.stock, '');

            calculerSaisie();
        } else {
            getEl('art_id').value = '';
            getEl('art_code').value = '';
            input.classList.remove('input-matched');
            hideAllHints();
        }
    } catch(err) { console.error('Article input error:', err); }
}

// =============================================
// AUTOCOMPLETE CATÉGORIE
// =============================================
function onSaisieCategorieInput() {
    try {
        var input = getEl('art_categorie');
        var val = input.value.trim();
        var match = null;
        for (var i = 0; i < FACT_CATEGORIES.length; i++) {
            if (FACT_CATEGORIES[i].nom.toLowerCase() === val.toLowerCase()) { match = FACT_CATEGORIES[i]; break; }
        }
        if (match) {
            getEl('art_categorie_id').value = match.id;
            getEl('art_categorie_nom').value = '';
            input.classList.add('input-matched');
        } else {
            getEl('art_categorie_id').value = '';
            getEl('art_categorie_nom').value = val;
            input.classList.remove('input-matched');
        }
    } catch(err) { console.error('Categorie input error:', err); }
}

// =============================================
// TYPE QUANTITÉ
// =============================================
function onSaisieTypeChange(skipFocus) {
    try {
        var type = getEl('art_type').value;
        var uniteFields = document.querySelectorAll('.champs-saisie-unite');
        var cartonDiv = getEl('cartonFields');
        if (type === 'CARTON') {
            for (var i = 0; i < uniteFields.length; i++) uniteFields[i].style.display = 'none';
            cartonDiv.style.display = 'block';
            if (!skipFocus) getEl('art_nb_cartons').focus();
        } else {
            for (var i = 0; i < uniteFields.length; i++) uniteFields[i].style.display = '';
            cartonDiv.style.display = 'none';
            if (!skipFocus) getEl('art_qte').focus();
        }
        calculerSaisie();
    } catch(err) { console.error('Type change error:', err); }
}

// =============================================
// CALCUL APERÇU
// =============================================
function calculerSaisie() {
    try {
        var type = getEl('art_type').value;
        var devise = getEl('devise').value;
        var total = 0, qteUnites = 0;
        if (type === 'CARTON') {
            var nc = parseFloat(getEl('art_nb_cartons').value) || 0;
            var ppc = parseFloat(getEl('art_pcs_carton').value) || 1;
            var ps = parseFloat(getEl('art_pcs_sup').value) || 0;
            var pc = parseFloat(getEl('art_prix_carton').value) || 0;
            var pps = parseFloat(getEl('art_prix_pcs_sup').value) || 0;
            var pu = ppc > 0 ? pc / ppc : 0;
            if (pps === 0 && ps > 0) pps = pu;
            qteUnites = (nc * ppc) + ps;
            total = (nc * pc) + (ps * pps);
            // Synchroniser le prix d'achat unitaire calculé
            getEl('art_prix_achat').value = Math.round(pu * 100) / 100;
        } else {
            qteUnites = parseFloat(getEl('art_qte').value) || 0;
            var pa = parseFloat(getEl('art_prix_achat').value) || 0;
            total = qteUnites * pa;
        }
        getEl('saisieTotal').textContent = 'Sous-total: ' + factFormatNumber(total) + (type === 'CARTON' ? ' (' + qteUnites + ' unités)' : '');
        if (devise === 'USD' && total > 0) {
            getEl('saisieTotalConv').textContent = factFormatNumber(total * factGetTaux());
            getEl('saisieConversion').style.display = 'inline';
        } else {
            getEl('saisieConversion').style.display = 'none';
        }
    } catch(err) { console.error('Calcul error:', err); }
}

// =============================================
// AJOUTER ARTICLE
// =============================================
function ajouterArticle() {
    try {
        var nom = getEl('art_nom').value.trim();
        if (!nom) { alert('Saisissez le nom de l\'article'); getEl('art_nom').focus(); return; }

        var type = getEl('art_type').value;
        var art = {
            article_id: getEl('art_id').value || null,
            code: getEl('art_code').value || '',
            nom: nom,
            description: '',
            categorie_id: getEl('art_categorie_id').value || null,
            categorie_nom: getEl('art_categorie_nom').value || '',
            type_quantite: type
        };

        if (type === 'CARTON') {
            art.nombre_cartons = parseInt(getEl('art_nb_cartons').value) || 0;
            art.pieces_par_carton = parseInt(getEl('art_pcs_carton').value) || 1;
            art.pieces_supplementaires = parseInt(getEl('art_pcs_sup').value) || 0;
            art.prix_achat_carton = parseFloat(getEl('art_prix_carton').value) || 0;
            art.prix_piece_sup = parseFloat(getEl('art_prix_pcs_sup').value) || 0;
            art.prix_vente = parseFloat(getEl('art_prix_vente_carton').value) || 0;
            art.prix_achat_unitaire = art.pieces_par_carton > 0 ? art.prix_achat_carton / art.pieces_par_carton : 0;
            if (art.prix_piece_sup === 0 && art.pieces_supplementaires > 0) art.prix_piece_sup = art.prix_achat_unitaire;
            art.quantite_unites = (art.nombre_cartons * art.pieces_par_carton) + art.pieces_supplementaires;
        } else {
            art.quantite_unites = parseInt(getEl('art_qte').value) || 0;
            art.prix_achat_unitaire = parseFloat(getEl('art_prix_achat').value) || 0;
            art.prix_vente = parseFloat(getEl('art_prix_vente').value) || 0;
            art.nombre_cartons = 0;
            art.pieces_par_carton = 1;
            art.prix_achat_carton = 0;
        }

        if (art.quantite_unites <= 0) { alert('La quantité doit être supérieure à 0'); return; }

        factArticlesAjoutes.push(art);
        factViderChamps();
        factRafraichirTableau();
        factMajResume();
        factSaveState();
        getEl('art_nom').focus();
    } catch(err) { console.error('Ajouter article error:', err); alert('Erreur: ' + err.message); }
}

// =============================================
// VIDER LES CHAMPS
// =============================================
function factViderChamps() {
    getEl('art_nom').value = '';
    getEl('art_nom').classList.remove('input-matched');
    getEl('art_id').value = '';
    getEl('art_code').value = '';
    getEl('art_categorie').value = '';
    getEl('art_categorie').classList.remove('input-matched');
    getEl('art_categorie_id').value = '';
    getEl('art_categorie_nom').value = '';
    getEl('art_type').value = 'UNITE';
    getEl('art_qte').value = '1';
    getEl('art_prix_achat').value = '0';
    getEl('art_prix_vente').value = '0';
    getEl('art_nb_cartons').value = '1';
    getEl('art_pcs_carton').value = '1';
    getEl('art_pcs_sup').value = '0';
    getEl('art_prix_carton').value = '0';
    getEl('art_prix_pcs_sup').value = '0';
    getEl('art_prix_vente_carton').value = '0';
    var uf = document.querySelectorAll('.champs-saisie-unite');
    for (var i = 0; i < uf.length; i++) uf[i].style.display = '';
    getEl('cartonFields').style.display = 'none';
    getEl('saisieTotal').textContent = 'Sous-total: 0';
    getEl('saisieConversion').style.display = 'none';
    hideAllHints();
}

// =============================================
// TABLEAU
// =============================================
function factRafraichirTableau() {
    var zone = getEl('tableArticlesZone');
    if (factArticlesAjoutes.length === 0) { zone.innerHTML = ''; return; }
    var html = '<table class="table-articles"><thead><tr>';
    html += '<th>#</th><th>Article</th><th>Type</th><th class="text-end">Qté</th><th class="text-end">P. Achat</th><th class="text-end">P. Vente</th><th class="text-end">Total</th><th></th>';
    html += '</tr></thead><tbody>';
    for (var i = 0; i < factArticlesAjoutes.length; i++) {
        var a = factArticlesAjoutes[i];
        var total = a.type_quantite === 'CARTON'
            ? (a.nombre_cartons * a.prix_achat_carton) + (a.pieces_supplementaires * (a.prix_piece_sup || a.prix_achat_unitaire))
            : a.quantite_unites * a.prix_achat_unitaire;
        var typeLabel = a.type_quantite === 'CARTON' ? a.nombre_cartons + ' crt (' + a.quantite_unites + ' pcs)' : 'Unité';
        var prixAchat = a.type_quantite === 'CARTON' ? a.prix_achat_carton : a.prix_achat_unitaire;
        html += '<tr>';
        html += '<td>' + (i + 1) + '</td>';
        html += '<td><strong>' + factEscapeHtml(a.nom) + '</strong>' + (a.article_id ? ' <span class="badge bg-success" style="font-size:.55rem;">existant</span>' : ' <span class="badge bg-warning text-dark" style="font-size:.55rem;">nouveau</span>') + '</td>';
        html += '<td>' + typeLabel + '</td>';
        html += '<td class="text-end">' + a.quantite_unites + '</td>';
        html += '<td class="text-end">' + factFormatNumber(prixAchat) + '</td>';
        html += '<td class="text-end">' + factFormatNumber(a.prix_vente) + '</td>';
        html += '<td class="text-end"><strong>' + factFormatNumber(total) + '</strong></td>';
        html += '<td><button type="button" class="btn btn-outline-danger btn-sm" onclick="supprimerArticle(' + i + ')" tabindex="-1"><i class="fas fa-trash"></i></button></td>';
        html += '</tr>';
    }
    html += '</tbody></table>';
    zone.innerHTML = html;
}

function supprimerArticle(index) {
    factArticlesAjoutes.splice(index, 1);
    factRafraichirTableau();
    factMajResume();
    factSaveState();
}

// =============================================
// RÉSUMÉ & JSON
// =============================================
function factMajResume() {
    var totalU = 0, montant = 0;
    for (var i = 0; i < factArticlesAjoutes.length; i++) {
        var a = factArticlesAjoutes[i];
        totalU += a.quantite_unites;
        if (a.type_quantite === 'CARTON') {
            montant += (a.nombre_cartons * a.prix_achat_carton) + (a.pieces_supplementaires * (a.prix_piece_sup || a.prix_achat_unitaire));
        } else {
            montant += a.quantite_unites * a.prix_achat_unitaire;
        }
    }
    getEl('nbArticles').textContent = factArticlesAjoutes.length;
    getEl('nbArticlesHeader').textContent = factArticlesAjoutes.length;
    getEl('totalUnites').textContent = totalU;
    getEl('montantTotal').textContent = factFormatNumber(montant);
    getEl('deviseTotal').textContent = getEl('devise').value;
    getEl('btnEnregistrer').disabled = (factArticlesAjoutes.length === 0);
    getEl('articles_json').value = JSON.stringify(factArticlesAjoutes);
}

// =============================================
// FOURNISSEUR
// =============================================
function onFournisseurInput() {
    try {
        var input = getEl('fournisseur_input');
        var val = input.value.trim();
        var match = null;
        for (var i = 0; i < FACT_FOURNISSEURS.length; i++) {
            if (FACT_FOURNISSEURS[i].nom.toLowerCase() === val.toLowerCase()) { match = FACT_FOURNISSEURS[i]; break; }
        }
        if (match) {
            getEl('fournisseur_id').value = match.id;
            getEl('fournisseur_nom').value = '';
            input.classList.add('input-matched');
        } else {
            getEl('fournisseur_id').value = '';
            getEl('fournisseur_nom').value = val;
            input.classList.remove('input-matched');
        }
    } catch(err) { console.error('Fournisseur error:', err); }
}

// =============================================
// VALIDATION FORMULAIRE
// =============================================
function validerFormulaire() {
    if (factArticlesAjoutes.length === 0) { alert('Veuillez ajouter au moins un article'); return false; }
    if (!getEl('numero_facture').value.trim()) { alert('Le numéro de facture est obligatoire'); return false; }
    getEl('articles_json').value = JSON.stringify(factArticlesAjoutes);
    factClearState();
    var btn = getEl('btnEnregistrer');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Enregistrement en cours...';
    return true;
}

// =============================================
// INIT
// =============================================
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Devise change
        getEl('devise').addEventListener('change', function() {
            getEl('info_conversion').style.display = this.value === 'USD' ? 'block' : 'none';
            calculerSaisie();
            factRafraichirTableau();
            factMajResume();
            factSaveState();
        });

        // Auto-save en-tête quand les champs changent
        var headerFields = ['numero_facture', 'date_facture', 'fournisseur_input'];
        for (var i = 0; i < headerFields.length; i++) {
            var el = getEl(headerFields[i]);
            if (el) el.addEventListener('change', factSaveState);
        }
        var notesEl = document.querySelector('input[name="notes"]');
        if (notesEl) notesEl.addEventListener('change', factSaveState);

        // Restaurer le brouillon
        var restored = factLoadState();
        getEl('art_nom').focus();

        console.log('✅ Facture JS OK - Articles:', FACT_ARTICLES.length, '- Catégories:', FACT_CATEGORIES.length, '- Fournisseurs:', FACT_FOURNISSEURS.length);
    } catch(err) {
        console.error('❌ Facture JS init error:', err);
    }
});
