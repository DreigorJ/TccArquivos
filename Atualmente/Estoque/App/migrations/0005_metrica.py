from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('App', '0004_comprarecorrente'),
    ]

    operations = [
        migrations.CreateModel(
            name='Metrica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True)),
                ('codigo', models.CharField(max_length=10, unique=True)),
                ('fixa', models.BooleanField(default=False)),
            ],
        ),
    ]