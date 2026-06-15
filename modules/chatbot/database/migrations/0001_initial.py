from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ChatbotDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, default=None, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('READY', 'Ready'), ('FAILED', 'Failed')], max_length=20)),
            ],
            options={
                'db_table': 'chatbot_documents',
                'ordering': ['-id'],
                'abstract': False,
                'managed': False,
            },
        ),
    ]
