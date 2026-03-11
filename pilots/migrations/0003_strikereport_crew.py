from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds the `crew` column that was defined in 0001_initial but never reached
    the production database (0001 was modified after it was applied).
    """

    dependencies = [
        ('pilots', '0002_strikereport_video'),
    ]

    operations = [
        migrations.AddField(
            model_name='strikereport',
            name='crew',
            field=models.CharField(
                choices=[
                    ('АКУЛА', 'АКУЛА'), ('БОЦМАН', 'БОЦМАН'),
                    ('ДЕМЕНТОР', 'ДЕМЕНТОР'), ('КАЙМАН', 'КАЙМАН'),
                    ('КАЖАН', 'КАЖАН'), ('КОСМОНАВТ', 'КОСМОНАВТ'),
                    ('КАПЕР', 'КАПЕР'), ('РАКЕТА', 'РАКЕТА'),
                    ('ПУГАЧ', 'ПУГАЧ'), ('ЗЛЮКА', 'ЗЛЮКА'),
                    ('СУЗУКІ', 'СУЗУКІ'), ('КРЕЧЕТ', 'КРЕЧЕТ'),
                    ('АКВІЛА', 'АКВІЛА'), ('ДЕВЕРСАНТ', 'ДЕВЕРСАНТ'),
                    ('АЛЬГІЗ', 'АЛЬГІЗ'), ('ПЕКАРЬ', 'ПЕКАРЬ'),
                    ('ПАЛІЙ', 'ПАЛІЙ'), ('АМІГО', 'АМІГО'),
                    ('ФАРАДЕЙ', 'ФАРАДЕЙ'), ('ГРИФ', 'ГРИФ'),
                    ('ХАНТЕР', 'ХАНТЕР'), ('СКАУТ', 'СКАУТ'),
                    ('СТУДЕНТ', 'СТУДЕНТ'), ('ГАРПІЯ', 'ГАРПІЯ'),
                    ('ЛЮТИЙ', 'ЛЮТИЙ'), ('ХАРОН', 'ХАРОН'),
                    ('Мікі', 'Мікі'), ('Амулет', 'Амулет'),
                    ('ШЕРШЕНЬ', 'ШЕРШЕНЬ'), ('ВОРОН', 'ВОРОН'),
                    ('КРОТ', 'КРОТ'),
                ],
                max_length=50,
                verbose_name='Екіпаж',
                default='',
            ),
            preserve_default=False,
        ),
    ]
