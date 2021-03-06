from django import forms
from django.conf import settings
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.urls import reverse_lazy


class MapboxGlWidget(BaseGeometryWidget):
    """
    An OpenLayers/OpenStreetMap-based widget.
    """
    template_name = 'gis/mapbox-gl.html'
    map_srid = 4326
    default_lon = 5
    default_lat = 47

    class Media:
        css = {
            'all': (
                settings.MAPBOX_GL_CSS,
            )
        }
        js = (
            settings.MAPBOX_GL_JS,
        )

    def __init__(self, attrs=None):
        super().__init__()
        for key in ('default_lon', 'default_lat'):
            self.attrs[key] = getattr(self, key)
        if attrs:
            self.attrs.update(attrs)

    @property
    def media(self):
        return (
            forms.Media(css=self.Media.css, js=self.Media.js)
            +
            forms.Media(js=(
                '{}?format=js'.format(reverse_lazy('gis_endpoints')),
                'maps/mapbox-gl-widget.js'))
        )

    def serialize(self, value):
        return value.json if value else ''


class AdminMapboxGlWidget(MapboxGlWidget):
    admin_site = True

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['admin_site'] = self.admin_site
        return context
