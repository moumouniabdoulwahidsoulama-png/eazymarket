"""
Met la base MySQL en utf8mb4 — le seul encodage qui accepte les emoji.

    python manage.py reparer_utf8mb4

cPanel crée souvent les bases en « utf8 » (utf8mb3), qui ne stocke que des
caractères sur 3 octets. Un drapeau 🇧🇫, un emoji dans le nom d'un produit ou
dans un message entre un client et un artisan en font 4 : MySQL refuse la
ligne avec « Incorrect string value ».

Cette commande convertit la base et toutes ses tables. Elle ne perd aucune
donnée et peut être relancée sans risque.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

COLLATION = "utf8mb4_unicode_ci"


class Command(BaseCommand):
    help = "Convertit la base MySQL et ses tables en utf8mb4 (support des emoji)."

    def add_arguments(self, parser):
        parser.add_argument("--simuler", action="store_true",
                            help="Montre ce qui serait fait, sans rien modifier")

    def handle(self, *args, **options):
        moteur = settings.DATABASES["default"]["ENGINE"]
        if "mysql" not in moteur:
            self.stdout.write(self.style.WARNING(
                f"Base {moteur.rsplit('.', 1)[-1]} : rien à faire, "
                "seul MySQL/MariaDB est concerné."
            ))
            return

        simuler = options["simuler"]
        nom_base = connection.settings_dict["NAME"]

        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.execute(
                "SELECT default_character_set_name, default_collation_name "
                "FROM information_schema.SCHEMATA WHERE schema_name = %s",
                [nom_base],
            )
            ligne = cursor.fetchone()
            charset_actuel = ligne[0] if ligne else "?"

            self.stdout.write(f"Serveur      : {version}")
            self.stdout.write(f"Base         : {nom_base}")
            self.stdout.write(f"Encodage     : {charset_actuel}")
            self.stdout.write("")

            if charset_actuel == "utf8mb4":
                self.stdout.write(self.style.SUCCESS("La base est déjà en utf8mb4."))
            elif simuler:
                self.stdout.write(f"[simulation] ALTER DATABASE → utf8mb4 / {COLLATION}")
            else:
                cursor.execute(
                    f"ALTER DATABASE `{nom_base}` "
                    f"CHARACTER SET utf8mb4 COLLATE {COLLATION}"
                )
                self.stdout.write(self.style.SUCCESS("Base convertie en utf8mb4."))

            cursor.execute(
                "SELECT table_name, table_collation FROM information_schema.TABLES "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                [nom_base],
            )
            tables = cursor.fetchall()

            a_convertir = [t for t, c in tables if not (c or "").startswith("utf8mb4")]
            deja = len(tables) - len(a_convertir)

            self.stdout.write("")
            self.stdout.write(f"{len(tables)} table(s) — {deja} déjà en utf8mb4, "
                              f"{len(a_convertir)} à convertir.")

            if simuler:
                for table in a_convertir:
                    self.stdout.write(f"  [simulation] {table}")
                return

            faites, echecs = 0, []
            for table in a_convertir:
                try:
                    cursor.execute(
                        f"ALTER TABLE `{table}` CONVERT TO "
                        f"CHARACTER SET utf8mb4 COLLATE {COLLATION}"
                    )
                    faites += 1
                except Exception as exc:  # noqa: BLE001
                    echecs.append((table, str(exc).split("\n")[0]))

            self.stdout.write("")
            if faites:
                self.stdout.write(self.style.SUCCESS(f"{faites} table(s) converties."))
            if echecs:
                self.stdout.write(self.style.ERROR(f"{len(echecs)} table(s) en échec :"))
                for table, message in echecs:
                    self.stdout.write(f"  {table} : {message}")
                self.stdout.write("")
                self.stdout.write(
                    "Si le message parle de « key was too long », votre serveur MySQL est\n"
                    "ancien. Demandez à LWS d'activer innodb_large_prefix et le format de\n"
                    "ligne DYNAMIC, ou de passer la base sur un serveur MariaDB récent."
                )
            else:
                self.stdout.write(self.style.SUCCESS(
                    "Tout est en utf8mb4 : les emoji, les accents et les caractères "
                    "africains passeront sans problème."
                ))
