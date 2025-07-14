from django.db import migrations

def migrate_produto_metrica(apps, schema_editor):
    Produto = apps.get_model('App', 'Produto')
    Metrica = apps.get_model('App', 'Metrica')
    for produto in Produto.objects.all():
        # Para garantir compatibilidade, trata codificação minúscula/maiuscula
        cod = produto.metrica.upper() if produto.metrica else None
        metrica_obj = Metrica.objects.filter(codigo__iexact=cod).first()
        if metrica_obj:
            produto.metrica_temp_id = metrica_obj.id
            produto.save()

class Migration(migrations.Migration):

    dependencies = [
        ('App', '0007_produto_metrica_fk'),
    ]

    operations = [
        migrations.RunPython(migrate_produto_metrica),
    ]