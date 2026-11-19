from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0006_add_complimentary_ticket'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guest',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
