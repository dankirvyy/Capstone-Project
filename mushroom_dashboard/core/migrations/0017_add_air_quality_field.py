# Generated migration for MQ-135 air quality sensor

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_dht22_sensor_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='sensorreading',
            name='air_quality_ppm',
            field=models.IntegerField(blank=True, help_text='Air quality from MQ-135 in PPM', null=True),
        ),
    ]
