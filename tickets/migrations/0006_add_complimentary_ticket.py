from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0005_add_verified_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='is_complimentary',
            field=models.BooleanField(
                default=False,
                help_text='Complimentary ticket — excluded from all dashboard counts.',
            ),
        ),
    ]
