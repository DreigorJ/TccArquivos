from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('App', '0006_create_metricas_fixas'),
    ]

    operations = [
        # Adiciona campo temporário
        migrations.AddField(
            model_name='produto',
            name='metrica_temp',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='App.metrica'),
        ),
    ]