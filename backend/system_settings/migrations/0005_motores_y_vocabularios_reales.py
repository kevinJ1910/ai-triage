from django.db import migrations, models

# El analizador solo llama a Gemini; GPT y Claude aparecian en la configuracion sin efecto.
LLM_WITHOUT_BACKEND = ('gpt-4o-mini', 'gpt-4o', 'claude-3-5-sonnet')


def to_real_options(apps, schema_editor):
    SystemConfiguration = apps.get_model('system_settings', 'SystemConfiguration')
    SystemConfiguration.objects.filter(active_llm_engine__in=LLM_WITHOUT_BACKEND).update(active_llm_engine='gemini-2.5-flash')
    SystemConfiguration.objects.exclude(active_ner_model__in=('auto', 'catalogo')).update(active_ner_model='auto')
    SystemConfiguration.objects.filter(snomed_version='SNOMED CT (Edicion en Espanol)').update(
        snomed_version='SNOMED CT International Edition')
    SystemConfiguration.objects.filter(icd10_version='ICD-10 (CIE-10)').update(icd10_version='CIE-10 (OMS)')


class Migration(migrations.Migration):

    dependencies = [
        ('system_settings', '0004_llm_engine_solo_modelos_disponibles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemconfiguration',
            name='active_llm_engine',
            field=models.CharField(choices=[('gemini-2.5-flash', 'Gemini 2.5 Flash'), ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite'), ('gemini-3.8-flash', 'Gemini 3.8 Flash')], default='gemini-2.5-flash', max_length=50),
        ),
        migrations.AlterField(
            model_name='systemconfiguration',
            name='active_ner_model',
            field=models.CharField(choices=[('auto', 'RoBERTa clinico + catalogo (si el modelo esta cargado)'), ('catalogo', 'Solo catalogo terminologico y LLM')], default='auto', max_length=60),
        ),
        migrations.AlterField(
            model_name='systemconfiguration',
            name='snomed_version',
            field=models.CharField(default='SNOMED CT International Edition', max_length=100),
        ),
        migrations.AlterField(
            model_name='systemconfiguration',
            name='icd10_version',
            field=models.CharField(default='CIE-10 (OMS)', max_length=100),
        ),
        migrations.RunPython(to_real_options, migrations.RunPython.noop),
    ]
