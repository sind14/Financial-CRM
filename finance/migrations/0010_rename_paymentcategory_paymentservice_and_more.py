import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0009_paymentcategory_payment_category_option'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name='PaymentCategory',
            new_name='PaymentService',
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='category',
            new_name='service',
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='category_option',
            new_name='service_option',
        ),
        migrations.AlterField(
            model_name='paymentservice',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='payment_services',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
