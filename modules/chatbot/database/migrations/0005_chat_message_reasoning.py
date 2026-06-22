from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0004_chat_message_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='reasoning',
            field=models.TextField(blank=True, default=''),
        ),
    ]
