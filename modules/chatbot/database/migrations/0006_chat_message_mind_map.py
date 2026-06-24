from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0005_chat_message_reasoning'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='mind_map',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
