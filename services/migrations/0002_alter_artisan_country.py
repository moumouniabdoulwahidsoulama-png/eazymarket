"""Le pays de l'artisan devient une vraie relation vers regions.Country.

On supprime l'ancien champ texte puis on crée la clé étrangère : une
conversion directe échouerait sur une base contenant déjà des artisans
(« Burkina Faso » n'est pas un identifiant).
"""

import django.db.models.deletion
from django.db import migrations, models


def rattacher_les_artisans(apps, schema_editor):
    """Rattache les artisans existants au pays par défaut."""
    Artisan = apps.get_model("services", "Artisan")
    Country = apps.get_model("regions", "Country")
    defaut = Country.objects.filter(is_default=True).first() or Country.objects.first()
    if defaut:
        Artisan.objects.filter(country__isnull=True).update(country=defaut)


class Migration(migrations.Migration):

    dependencies = [
        ("regions", "0001_initial"),
        ("services", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="artisan", name="country"),
        migrations.AddField(
            model_name="artisan",
            name="country",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="artisans",
                to="regions.country",
                verbose_name="Pays",
            ),
        ),
        migrations.RunPython(rattacher_les_artisans, migrations.RunPython.noop),
    ]
