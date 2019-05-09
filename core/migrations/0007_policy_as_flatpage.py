# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-02-13 16:43
from __future__ import unicode_literals

from django.db import migrations
from django.template.loader import get_template


def create_initial_policy(app_registry, schema_editor):
    Policy = app_registry.get_model('core', 'Policy')
    template = 'pages/snippets/privacy_policy_initial.html'

    content = get_template(template).template.source
    Policy.objects.create(url='/privacy-policy-2018-001/', title='Privacy Policy (1st revision)', content=content)


def remove_initial_policy(app_registry, schema_editor):
    Policy = app_registry.get_model('core', 'Policy')
    Policy.objects.filter(url='/privacy-policy-2018-001/').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_geo_api_keys'),
    ]

    operations = [
        migrations.RunPython(create_initial_policy, reverse_code=remove_initial_policy),
    ]