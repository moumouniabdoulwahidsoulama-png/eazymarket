#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'audit du projet EazyMarket
Vérifie tous les fichiers, templates et URLs
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

# Couleurs pour la console
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.HEADER}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

class Audit:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.errors = []
        self.warnings = []
        self.success = []
        self.templates_found = []
        self.views_found = []
        self.urls_found = []
        self.encoding_errors = []
        
    def run(self):
        print_header("🔍 AUDIT COMPLET - EazyMarket")
        print(f"📁 Dossier: {self.base_dir}")
        print(f"📅 Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        
        # 1. Vérifier les templates
        self.check_templates()
        
        # 2. Vérifier les fichiers d'encodage
        self.check_encoding()
        
        # 3. Vérifier les URLs
        self.check_urls()
        
        # 4. Vérifier les vues
        self.check_views()
        
        # 5. Vérifier les modèles
        self.check_models()
        
        # 6. Générer le rapport
        self.generate_report()
        
        return self.errors, self.warnings
    
    def check_templates(self):
        print_header("📄 1. VÉRIFICATION DES TEMPLATES")
        
        template_dirs = [
            'templates',
            'accounts/templates',
            'products/templates',
            'cart/templates',
            'orders/templates',
            'services/templates',
            'notifications/templates',
        ]
        
        required_templates = {
            'base.html': 'Template de base',
            'accounts/register.html': 'Inscription',
            'accounts/login.html': 'Connexion',
            'accounts/profile.html': 'Profil',
            'accounts/seller_dashboard.html': 'Dashboard vendeur',
            'accounts/delivery_dashboard.html': 'Dashboard livreur',
            'accounts/admin_dashboard.html': 'Dashboard admin',
            'products/home.html': 'Accueil produits',
            'products/product_detail.html': 'Détail produit',
            'cart/cart.html': 'Panier',
            'orders/checkout.html': 'Validation commande',
            'orders/my_orders.html': 'Mes commandes',
            'orders/order_detail.html': 'Détail commande',
            'services/services_home.html': 'Accueil services',
            'services/artisan_list.html': 'Liste artisans',
            'services/artisan_detail.html': 'Détail artisan',
            'services/request_service.html': 'Demande service',
            'services/my_requests.html': 'Mes demandes',
            'services/artisan_dashboard.html': 'Dashboard artisan',
            'services/subscribe.html': 'Abonnement',
            'services/register_artisan.html': 'Inscription artisan',
            'services/leave_review.html': 'Laisser avis',
            'notifications/list.html': 'Notifications',
        }
        
        for template, description in required_templates.items():
            found = False
            for base in template_dirs:
                path = self.base_dir / base / template
                if path.exists():
                    found = True
                    break
            
            if found:
                print_success(f"{template} - {description}")
            else:
                print_error(f"{template} - {description} (MANQUANT)")
                self.errors.append(f"Template manquant: {template}")
        
        # Lister tous les templates trouvés
        print_info("\nTemplates trouvés:")
        for base in template_dirs:
            dir_path = self.base_dir / base
            if dir_path.exists():
                for file in dir_path.rglob('*.html'):
                    rel_path = file.relative_to(self.base_dir)
                    print(f"  📄 {rel_path}")
                    self.templates_found.append(str(rel_path))
    
    def check_encoding(self):
        print_header("🔤 2. VÉRIFICATION DE L'ENCODAGE")
        
        extensions = ['.html', '.py', '.txt', '.css', '.js']
        encoding_errors = []
        
        for ext in extensions:
            for file in self.base_dir.rglob(f'*{ext}'):
                if 'venv' in str(file) or '__pycache__' in str(file) or '.git' in str(file):
                    continue
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        f.read()
                except UnicodeDecodeError as e:
                    print_error(f"Erreur d'encodage: {file}")
                    print(f"   {e}")
                    encoding_errors.append(str(file))
                    self.encoding_errors.append(str(file))
                except Exception:
                    pass
        
        if encoding_errors:
            print_warning(f"{len(encoding_errors)} fichiers ont des problèmes d'encodage")
            for f in encoding_errors:
                print(f"  📄 {f}")
        else:
            print_success("Aucun problème d'encodage détecté")
    
    def check_urls(self):
        print_header("🔗 3. VÉRIFICATION DES URLs")
        
        url_files = [
            'EazyMarket/urls.py',
            'accounts/urls.py',
            'products/urls.py',
            'cart/urls.py',
            'orders/urls.py',
            'services/urls.py',
            'notifications/urls.py',
        ]
        
        for url_file in url_files:
            path = self.base_dir / url_file
            if path.exists():
                print_success(f"✅ {url_file}")
                self.urls_found.append(url_file)
                
                # Vérifier les imports
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'urlpatterns' not in content:
                            print_warning(f"   ⚠️  urlpatterns non trouvé dans {url_file}")
                except:
                    pass
            else:
                print_error(f"❌ {url_file} (MANQUANT)")
                self.errors.append(f"URL manquant: {url_file}")
    
    def check_views(self):
        print_header("👁️ 4. VÉRIFICATION DES VUES")
        
        view_files = [
            'accounts/views.py',
            'products/views.py',
            'cart/views.py',
            'orders/views.py',
            'services/views.py',
            'notifications/views.py',
        ]
        
        for view_file in view_files:
            path = self.base_dir / view_file
            if path.exists():
                print_success(f"✅ {view_file}")
                self.views_found.append(view_file)
                
                # Vérifier les fonctions
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        functions = re.findall(r'def\s+(\w+)\s*\(', content)
                        if functions:
                            print_info(f"   Fonctions trouvées: {', '.join(functions[:5])}")
                            if len(functions) > 5:
                                print(f"   ... et {len(functions)-5} autres")
                except:
                    pass
            else:
                print_error(f"❌ {view_file} (MANQUANT)")
                self.errors.append(f"Vue manquante: {view_file}")
    
    def check_models(self):
        print_header("📊 5. VÉRIFICATION DES MODÈLES")
        
        model_files = [
            'accounts/models.py',
            'products/models.py',
            'cart/models.py',
            'orders/models.py',
            'services/models.py',
            'notifications/models.py',
        ]
        
        for model_file in model_files:
            path = self.base_dir / model_file
            if path.exists():
                print_success(f"✅ {model_file}")
                
                # Compter les classes
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        classes = re.findall(r'class\s+(\w+)\s*\(', content)
                        if classes:
                            print_info(f"   Classes: {', '.join(classes)}")
                except:
                    pass
            else:
                print_error(f"❌ {model_file} (MANQUANT)")
                self.errors.append(f"Modèle manquant: {model_file}")
    
    def generate_report(self):
        print_header("📋 6. RAPPORT D'AUDIT")
        
        print(f"{Colors.BOLD}Statistiques:{Colors.END}")
        print(f"  📄 Templates: {len(self.templates_found)}")
        print(f"  🔗 URLs: {len(self.urls_found)}")
        print(f"  👁️ Vues: {len(self.views_found)}")
        print(f"  🔴 Erreurs: {len(self.errors)}")
        print(f"  🟡 Avertissements: {len(self.warnings)}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}🔴 Erreurs détectées:{Colors.END}")
            for err in self.errors:
                print(f"  ❌ {err}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}🟡 Avertissements:{Colors.END}")
            for warn in self.warnings:
                print(f"  ⚠️  {warn}")
        
        if self.encoding_errors:
            print(f"\n{Colors.RED}{Colors.BOLD}🔤 Problèmes d'encodage:{Colors.END}")
            for f in self.encoding_errors:
                print(f"  📄 {f}")
                print(f"     💡 Solution: Ouvrez le fichier dans un éditeur et sauvegardez en UTF-8")
        
        # Générer le fichier de rapport
        report_path = self.base_dir / 'audit_report.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"RAPPORT D'AUDIT - EazyMarket\n")
            f.write(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            
            f.write("TEMPLATES TROUVÉS:\n")
            for t in sorted(self.templates_found):
                f.write(f"  - {t}\n")
            
            f.write("\nURLS TROUVÉES:\n")
            for u in self.urls_found:
                f.write(f"  - {u}\n")
            
            f.write("\nERREURS:\n")
            for err in self.errors:
                f.write(f"  - {err}\n")
            
            if self.encoding_errors:
                f.write("\nPROBLÈMES D'ENCODAGE:\n")
                for err in self.encoding_errors:
                    f.write(f"  - {err}\n")
        
        print(f"\n{Colors.GREEN}✅ Rapport généré: audit_report.txt{Colors.END}")
        
        if not self.errors and not self.encoding_errors:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Tous les fichiers sont en place et correctement encodés !{Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}💡 Corrigez les erreurs puis relancez l'audit{Colors.END}")

def fix_encoding(file_path):
    """Tente de corriger l'encodage d'un fichier"""
    try:
        # Essayer de lire avec latin-1
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()
        
        # Réécrire avec UTF-8
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except:
        return False

if __name__ == "__main__":
    audit = Audit()
    errors, warnings = audit.run()
    
    # Si des erreurs d'encodage sont détectées, on propose de les corriger
    if audit.encoding_errors:
        print("\n" + "="*60)
        print("🔧 Voulez-vous corriger automatiquement les problèmes d'encodage ?")
        response = input("(o/n): ").strip().lower()
        if response == 'o':
            for file_path in audit.encoding_errors:
                if fix_encoding(file_path):
                    print_success(f"Corrigé: {file_path}")
                else:
                    print_error(f"Échec: {file_path}")
            print("\n✅ Correction terminée. Relancez l'audit pour vérifier.")
    
    sys.exit(0 if not errors else 1)