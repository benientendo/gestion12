// Script personnalisé pour Gestion Magazin

document.addEventListener('DOMContentLoaded', function() {
    // Initialisation des tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Animation pour les cartes du tableau de bord
    const dashboardCards = document.querySelectorAll('.card-dashboard');
    dashboardCards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in');
    });
    
    // Fonctions pour les actions des articles
    window.voirDetails = function(id) {
        // Afficher les détails de l'article dans un modal
        fetch(`/api/articles/${id}/`)
            .then(response => response.json())
            .then(data => {
                const detailsModal = new bootstrap.Modal(document.getElementById('detailsArticleModal'));
                
                // Remplir les détails dans le modal
                document.getElementById('detailsNom').textContent = data.nom;
                document.getElementById('detailsCode').textContent = data.code;
                document.getElementById('detailsCategorie').textContent = data.categorie.nom;
                document.getElementById('detailsPrix').textContent = `${data.prix_vente} CDF`;
                document.getElementById('detailsStock').textContent = data.quantite_stock;
                document.getElementById('detailsDescription').textContent = data.description || 'Aucune description';
                
                // Afficher le modal
                detailsModal.show();
            })
            .catch(error => {
                console.error('Erreur lors de la récupération des détails:', error);
                showAlert('Erreur lors de la récupération des détails de l\'article', 'danger');
            });
    };
    
    window.editerArticle = function(id) {
        // Récupérer les données de l'article pour le formulaire d'édition
        fetch(`/api/articles/${id}/`)
            .then(response => response.json())
            .then(data => {
                const editModal = new bootstrap.Modal(document.getElementById('editerArticleModal'));
                
                // Remplir le formulaire avec les données
                const form = document.getElementById('editArticleForm');
                form.elements['id'].value = data.id;
                form.elements['code'].value = data.code;
                form.elements['nom'].value = data.nom;
                form.elements['categorie'].value = data.categorie.id;
                form.elements['prix_vente'].value = data.prix_vente;
                form.elements['description'].value = data.description || '';
                
                // Afficher le modal
                editModal.show();
            })
            .catch(error => {
                console.error('Erreur lors de la récupération des données pour édition:', error);
                showAlert('Erreur lors de la récupération des données de l\'article', 'danger');
            });
    };
    
    window.supprimerArticle = function(id) {
        // Confirmer la suppression
        const confirmModal = new bootstrap.Modal(document.getElementById('confirmSupprimerModal'));
        document.getElementById('confirmSupprimerBtn').onclick = function() {
            // Envoyer la requête de suppression
            fetch(`/api/articles/${id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (response.ok) {
                    // Fermer le modal et recharger la page
                    confirmModal.hide();
                    showAlert('Article supprimé avec succès', 'success');
                    setTimeout(() => location.reload(), 1000);
                } else {
                    throw new Error('Erreur lors de la suppression');
                }
            })
            .catch(error => {
                console.error('Erreur lors de la suppression:', error);
                showAlert('Erreur lors de la suppression de l\'article', 'danger');
            });
        };
        
        // Afficher le modal de confirmation
        confirmModal.show();
    };
    
    // Fonction pour afficher des alertes
    window.showAlert = function(message, type = 'info') {
        const alertsContainer = document.querySelector('.alerts-container') || createAlertsContainer();
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.appendChild(alert);
        
        // Auto-fermeture après 5 secondes
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    };
    
    // Créer un conteneur pour les alertes s'il n'existe pas
    function createAlertsContainer() {
        const container = document.createElement('div');
        container.className = 'alerts-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
        return container;
    }
    
    // Récupérer le token CSRF
    function getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    // Gérer les soumissions de formulaire avec fetch API
    document.querySelectorAll('form[data-fetch="true"]').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            const url = form.action;
            const method = form.dataset.method || 'POST';
            
            fetch(url, {
                method: method,
                body: formData,
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                }
                throw new Error('Erreur lors de la soumission du formulaire');
            })
            .then(data => {
                if (data.success) {
                    showAlert(data.message || 'Opération réussie', 'success');
                    
                    // Fermer les modals si présents
                    const modal = bootstrap.Modal.getInstance(form.closest('.modal'));
                    if (modal) modal.hide();
                    
                    // Recharger la page après un court délai
                    if (form.dataset.reload === 'true') {
                        setTimeout(() => location.reload(), 1000);
                    }
                } else {
                    showAlert(data.message || 'Une erreur s\'est produite', 'danger');
                }
            })
            .catch(error => {
                console.error('Erreur:', error);
                showAlert('Une erreur s\'est produite lors de la soumission du formulaire', 'danger');
            });
        });
    });
    
    // Navigation AJAX entre les pages de rapports (rapports caisse, articles négociés, retours)
    function loadRapportsSection(url, pushState) {
        const contentContainer = document.querySelector('.container-fluid.py-4');
        if (!contentContainer) {
            // Si la structure attendue n'est pas trouvée, on repasse en navigation classique
            window.location.href = url;
            return;
        }

        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('Erreur lors du chargement de la page');
            }
            return response.text();
        })
        .then(function(html) {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newContent = doc.querySelector('.container-fluid.py-4');
            if (!newContent) {
                window.location.href = url;
                return;
            }

            // Remplacer le contenu principal
            contentContainer.replaceWith(newContent);

            // Mettre à jour les messages flash
            const newMessages = doc.querySelector('.messages');
            const currentMessages = document.querySelector('.messages');
            if (currentMessages) {
                currentMessages.innerHTML = newMessages ? newMessages.innerHTML : '';
            }

            // Réinitialiser les tooltips Bootstrap éventuels
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });

            // Remonter en haut de la page
            window.scrollTo({ top: 0, behavior: 'smooth' });

            // Réinitialiser la navigation AJAX sur le nouveau contenu
            initRapportsAjaxNavigation();

            // Mettre à jour l'URL dans l'historique si nécessaire
            if (pushState) {
                history.pushState({ rapportsAjax: true }, '', url);
            }
        })
        .catch(function(error) {
            console.error('Erreur de navigation AJAX:', error);
            window.location.href = url;
        });
    }

    function initRapportsAjaxNavigation() {
        const navGroup = document.querySelector('.btn-group[aria-label="Navigation rapports"]');
        if (!navGroup) {
            return;
        }

        // Intercepter les clics sur les trois onglets
        navGroup.addEventListener('click', function(event) {
            const link = event.target.closest('a');
            if (!link) {
                return;
            }

            const url = link.getAttribute('href');
            if (!url) {
                return;
            }

            // Laisser le comportement normal pour clic milieu / Ctrl+clic
            if (event.button === 1 || event.metaKey || event.ctrlKey) {
                return;
            }

            event.preventDefault();
            loadRapportsSection(url, true);
        });

        // Gérer le bouton retour/avant du navigateur
        window.addEventListener('popstate', function() {
            if (!document.querySelector('.btn-group[aria-label="Navigation rapports"]')) {
                return;
            }
            loadRapportsSection(location.href, false);
        });
    }

    function initGlobalRapportsModalsHandlers() {
        document.addEventListener('show.bs.modal', function(event) {
            var modal = event.target;
            var trigger = event.relatedTarget;
            if (!trigger) {
                return;
            }

            // Détail rapport de caisse
            if (modal.id === 'rapportDetailModal') {
                var date = trigger.getAttribute('data-date') || '';
                var terminal = trigger.getAttribute('data-terminal') || '';
                var depense = trigger.getAttribute('data-depense') || '';
                var devise = trigger.getAttribute('data-devise') || '';
                var detail = trigger.getAttribute('data-detail') || '';
                var appliquee = trigger.getAttribute('data-appliquee') === '1';
                var appliquerUrl = trigger.getAttribute('data-appliquer-url') || '#';

                var dateEl = modal.querySelector('#modalRapportDate');
                var terminalEl = modal.querySelector('#modalRapportTerminal');
                var depenseEl = modal.querySelector('#modalRapportDepense');
                var detailEl = modal.querySelector('#modalRapportDetail');
                var appliqueeInfo = modal.querySelector('#modalRapportAppliqueeInfo');
                var appliquerBtn = modal.querySelector('#appliquerDepenseButton');
                var form = modal.querySelector('#appliquerDepenseForm');

                if (dateEl) {
                    dateEl.textContent = date;
                }
                if (terminalEl) {
                    terminalEl.textContent = terminal;
                }
                if (depenseEl) {
                    depenseEl.textContent = depense + ' ' + devise;
                }
                if (detailEl) {
                    detailEl.textContent = detail;
                }

                if (form) {
                    form.setAttribute('action', appliquerUrl);
                }

                if (appliquee) {
                    if (appliquerBtn) {
                        appliquerBtn.classList.add('d-none');
                    }
                    if (appliqueeInfo) {
                        appliqueeInfo.classList.remove('d-none');
                    }
                } else {
                    if (appliquerBtn) {
                        appliquerBtn.classList.remove('d-none');
                    }
                    if (appliqueeInfo) {
                        appliqueeInfo.classList.add('d-none');
                    }
                }
            }

            // Détail article négocié
            if (modal.id === 'negociationDetailModal') {
                var dateNeg = trigger.getAttribute('data-date') || '';
                var terminalNeg = trigger.getAttribute('data-terminal') || '';
                var articleNeg = trigger.getAttribute('data-article') || '';
                var codeNeg = trigger.getAttribute('data-code') || '';
                var quantiteStr = trigger.getAttribute('data-quantite') || '0';
                var montantStr = trigger.getAttribute('data-montant') || '0';
                var deviseNeg = trigger.getAttribute('data-devise') || '';
                var motifNeg = trigger.getAttribute('data-motif') || '';
                var referenceNeg = trigger.getAttribute('data-reference') || '';
                var appliquerUrlNeg = trigger.getAttribute('data-appliquer-url') || '#';

                var quantite = parseInt(quantiteStr, 10) || 0;
                var montant = parseFloat(montantStr.replace(',', '.')) || 0;
                var total = quantite * montant;

                var dateElNeg = modal.querySelector('#modalNegociationDate');
                var terminalElNeg = modal.querySelector('#modalNegociationTerminal');
                var articleElNeg = modal.querySelector('#modalNegociationArticle');
                var codeElNeg = modal.querySelector('#modalNegociationCode');
                var quantiteElNeg = modal.querySelector('#modalNegociationQuantite');
                var montantElNeg = modal.querySelector('#modalNegociationMontant');
                var totalElNeg = modal.querySelector('#modalNegociationTotal');
                var motifElNeg = modal.querySelector('#modalNegociationMotif');
                var referenceElNeg = modal.querySelector('#modalNegociationReference');
                var formNeg = modal.querySelector('#appliquerNegociationForm');

                if (dateElNeg) dateElNeg.textContent = dateNeg;
                if (terminalElNeg) terminalElNeg.textContent = terminalNeg;
                if (articleElNeg) articleElNeg.textContent = articleNeg;
                if (codeElNeg) codeElNeg.textContent = codeNeg;
                if (quantiteElNeg) quantiteElNeg.textContent = quantite;
                if (montantElNeg) montantElNeg.textContent = montant.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2}) + ' ' + deviseNeg;
                if (totalElNeg) totalElNeg.textContent = total.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 2}) + ' ' + deviseNeg;
                if (motifElNeg) motifElNeg.textContent = motifNeg || '-';
                if (referenceElNeg) referenceElNeg.textContent = referenceNeg || '-';

                if (formNeg) {
                    formNeg.setAttribute('action', appliquerUrlNeg);
                }
            }
        });
    }

    function initRapportsAjaxApplyForms() {
        document.addEventListener('submit', function(event) {
            var form = event.target;
            if (!form) {
                return;
            }

            if (form.id === 'appliquerDepenseForm' || form.id === 'appliquerNegociationForm') {
                event.preventDefault();

                var submitBtn = form.querySelector('button[type="submit"]');
                var originalText = '';
                if (submitBtn) {
                    originalText = submitBtn.innerHTML;
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Traitement...';
                }

                var formData = new FormData(form);

                fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCSRFToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Erreur lors de l\'application');
                    }

                    // Recharger la section actuelle pour refléter les changements et les messages
                    loadRapportsSection(window.location.href, false);

                    // Fermer le modal si présent
                    var modalEl = form.closest('.modal');
                    if (modalEl) {
                        var modalInstance = bootstrap.Modal.getInstance(modalEl);
                        if (modalInstance) {
                            modalInstance.hide();
                        }
                    }
                })
                .catch(function(error) {
                    console.error('Erreur application négociation/rapport:', error);
                    showAlert('Erreur lors de l\'application. Veuillez réessayer.', 'danger');
                })
                .finally(function() {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalText;
                    }
                });
            }
        });
    }

    // Initialiser la navigation AJAX et les handlers globaux de modals sur les pages concernées
    initRapportsAjaxNavigation();
    initGlobalRapportsModalsHandlers();
    initRapportsAjaxApplyForms();

    // Gestion du menu mobile
    const toggleSidebarBtn = document.getElementById('toggleSidebar');
    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', function() {
            document.querySelector('.sidebar').classList.toggle('show-mobile');
        });
    }
    
    // Animation du loader
    const loader = document.querySelector('.loader-wrapper');
    if (loader) {
        window.addEventListener('load', function() {
            loader.style.opacity = '0';
            setTimeout(() => {
                loader.style.display = 'none';
            }, 500);
        });
    }
});
