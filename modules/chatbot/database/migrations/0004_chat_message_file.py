import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0003_chat_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessageFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, default=None, null=True)),
                ('media_id', models.BigIntegerField(db_index=True)),
                ('gemini_uri', models.TextField(blank=True, default='')),
                ('pushed_at', models.DateTimeField(blank=True, default=None, null=True)),
                ('conversation', models.ForeignKey(db_column='conversation_id', on_delete=django.db.models.deletion.CASCADE, related_name='message_files', to='chatbot.chatconversation')),
                ('message', models.ForeignKey(db_column='message_id', on_delete=django.db.models.deletion.CASCADE, related_name='files', to='chatbot.chatmessage')),
            ],
            options={
                'db_table': 'chatbot_message_files',
                'ordering': ['id'],
                'abstract': False,
            },
        ),
    ]
