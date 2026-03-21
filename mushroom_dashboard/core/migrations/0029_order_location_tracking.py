from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_customeradminmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='current_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='current_location_address',
            field=models.TextField(blank=True, help_text='Current delivery address/area update'),
        ),
        migrations.AddField(
            model_name='order',
            name='current_location_status',
            field=models.CharField(blank=True, help_text='Current delivery status/location note', max_length=120),
        ),
        migrations.AddField(
            model_name='order',
            name='current_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='location_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
