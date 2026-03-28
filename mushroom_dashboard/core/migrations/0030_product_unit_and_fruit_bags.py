from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_order_location_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='product_type',
            field=models.CharField(
                choices=[
                    ('fresh', 'Fresh Mushrooms'),
                    ('cooked', 'Cooked / Ready-to-Eat'),
                    ('fruit_bags', 'Fruit Bags'),
                ],
                default='fresh',
                help_text='Type of product',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='price_per_kg',
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text='Unit price based on the selected unit',
                max_digits=6,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='unit',
            field=models.CharField(
                choices=[
                    ('kg', 'per kg'),
                    ('pack', 'per pack'),
                    ('bag', 'per bag'),
                    ('piece', 'per piece'),
                ],
                default='kg',
                help_text='Unit of measurement for pricing and quantity',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='unit',
            field=models.CharField(
                choices=[
                    ('kg', 'per kg'),
                    ('pack', 'per pack'),
                    ('bag', 'per bag'),
                    ('piece', 'per piece'),
                ],
                default='kg',
                max_length=10,
            ),
        ),
    ]
