from django.db import migrations

def create_metricas_fixas(apps, schema_editor):
    Metrica = apps.get_model('App', 'Metrica')
    metricas_fixas = [
        {"codigo": "UN", "nome": "Unidade"},
        {"codigo": "KG", "nome": "Quilo"},
        {"codigo": "L", "nome": "Litro"}
    ]
    for metrica in metricas_fixas:
        if not Metrica.objects.filter(codigo=metrica["codigo"]).exists():
            Metrica.objects.create(
                nome=metrica["nome"],
                codigo=metrica["codigo"],
                fixa=True
            )

class Migration(migrations.Migration):

    dependencies = [
        ('App', '0005_metrica'),
    ]

    operations = [
        migrations.RunPython(create_metricas_fixas),
    ]