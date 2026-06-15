import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0002_chat_conversation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, default=None, null=True)),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=20)),
                ('content', models.TextField(blank=True, default='')),
                ('citations', models.JSONField(blank=True, default=None, null=True)),
                ('status', models.CharField(choices=[('PROCESSING', 'Processing'), ('SUCCESS', 'Success'), ('ERROR', 'Error')], default='SUCCESS', max_length=20)),
                ('conversation', models.ForeignKey(db_column='conversation_id', on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='chatbot.chatconversation')),
            ],
            options={
                'db_table': 'chatbot_messages',
                'ordering': ['id'],
                'abstract': False,
            },
        ),
    ]
