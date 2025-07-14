from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('App', '0008_migrar_metricas_produto'),
    ]

    operations = [
        # Remove campo antigo
        migrations.RemoveField(
            model_name='produto',
            name='metrica',
        ),
        # Renomeia campo temp para definitivo
        migrations.RenameField(
            model_name='produto',
            old_name='metrica_temp',
            new_name='metrica',
        ),
        # Garante que seja obrigatória e configurada corretamente
        migrations.AlterField(
            model_name='produto',
            name='metrica',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='produtos', to='App.metrica'),
        ),
    ]