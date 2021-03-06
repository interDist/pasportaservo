# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-05-02 18:48
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.contrib.gis.geos import Point
# from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


def populate_location(app_registry, schema_editor):
    Place = app_registry.get_model('hosting', 'Place')
    places = Place._default_manager.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).only('latitude', 'longitude').order_by('pk')
    for place in places:
        print(place.pk, place.longitude, place.latitude)
        place.location = Point(place.longitude, place.latitude)
        if not place.location.empty:
            place.save()


class Migration(migrations.Migration):

    dependencies = [
        ('hosting', '0039_merge_20170613_1341'),
    ]

    operations = [
        # sudo -u postgres psql
        # postgres=# CREATE EXTENSION postgis;
        #
        # CreateExtension('postgis'),

        migrations.AddField(
            model_name='place',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326, verbose_name='location'),
        ),

        migrations.RunPython(populate_location),
    ]
