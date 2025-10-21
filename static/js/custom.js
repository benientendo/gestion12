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
