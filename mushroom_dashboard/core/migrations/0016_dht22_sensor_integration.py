# Generated migration for DHT22 sensor integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_userprofile_latitude_userprofile_longitude'),
    ]

    operations = [
        # Modify SensorReading table to support DHT22 data
        migrations.AlterField(
            model_name='sensorreading',
            name='temperature',
            field=models.DecimalField(decimal_places=1, help_text='Temperature in Celsius', max_digits=4),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='humidity',
            field=models.DecimalField(decimal_places=1, help_text='Relative humidity percentage', max_digits=4),
        ),
        migrations.AlterField(
            model_name='sensorreading',
            name='co2_ppm',
            field=models.IntegerField(blank=True, help_text='CO2 level in PPM (optional)', null=True),
        ),
        migrations.AddField(
            model_name='sensorreading',
            name='device_id',
            field=models.CharField(default='DHT22_ESP32', help_text='Sensor device identifier', max_length=50),
        ),
        migrations.AlterModelOptions(
            name='sensorreading',
            options={'ordering': ['-timestamp']},
        ),
        migrations.AddIndex(
            model_name='sensorreading',
            index=models.Index(fields=['-timestamp'], name='core_sensor_timesta_idx'),
        ),
    ]
