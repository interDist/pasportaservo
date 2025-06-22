from django.contrib.sites.models import Site
from django.template import Context, Template
from django.test import RequestFactory, TestCase, tag


@tag('templatetags')
class DomainTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request_factory = RequestFactory()
        cls.template_sans_url = Template("{% load domain %}{% domain %}")
        cls.template_with_url = Template("{% load domain %}{% domain '/418?I=am&Teapot' %}")

    def setUp(self):
        first_site = Site.objects.get(id=1)
        first_site.name, first_site.domain = 'MyTestServer', 'mytestsrv'
        # We cannot use QS.update() because it does not trigger the `save` signal
        # (which clears the site cache; see django.contrib.sites.models.SiteManager).
        first_site.save()
        Site.objects.create(name='TestPS', domain='test.pasportaservo.org.mondo')

    def test_through_request(self):
        # A typical web page template has a 'request' context variable and the values
        # of scheme+host are expected to be taken from the Request.
        request = self.request_factory.get('/404')
        page = self.template_sans_url.render(Context({'request': request}))
        self.assertEqual(page, "http://mytestsrv")
        page = self.template_with_url.render(Context({'request': request}))
        self.assertEqual(page, "http://mytestsrv/418?I=am&amp;Teapot")

        request = self.request_factory.get('/404', secure=True)
        page = self.template_sans_url.render(Context({'request': request}))
        self.assertEqual(page, "https://mytestsrv")
        page = self.template_with_url.render(Context({'request': request}))
        self.assertEqual(page, "https://mytestsrv/418?I=am&amp;Teapot")

    def test_through_django_email(self):
        # A Django email template has 'protocol' & 'domain' context variables and the
        # values of scheme+host are expected to be matching these variables.
        page = self.template_sans_url.render(Context({'protocol': "xkcd", 'domain': "initialism"}))
        self.assertEqual(page, "xkcd://initialism")
        page = self.template_with_url.render(Context({'protocol': "xkcd", 'domain': "initialism"}))
        self.assertEqual(page, "xkcd://initialism/418?I=am&amp;Teapot")

    def test_through_postman_email(self):
        # A Postman email template has a 'site' context variable and the value of the
        # host is expected to be extracted from the Site, while the scheme is expected
        # to vary according to the hostname.
        page = self.template_sans_url.render(Context({'site': Site.objects.get(name='MyTestServer')}))
        self.assertEqual(page, "http://mytestsrv")
        page = self.template_with_url.render(Context({'site': Site.objects.get(name='MyTestServer')}))
        self.assertEqual(page, "http://mytestsrv/418?I=am&amp;Teapot")

        page = self.template_sans_url.render(Context({'site': Site.objects.get(name='TestPS')}))
        self.assertEqual(page, "https://test.pasportaservo.org.mondo")
        page = self.template_with_url.render(Context({'site': Site.objects.get(name='TestPS')}))
        self.assertEqual(page, "https://test.pasportaservo.org.mondo/418?I=am&amp;Teapot")

    def test_fallback(self):
        # When no suitable context variables are available, the result is expected to
        # be a fallback, dependent on the DEBUG status (True = dev/test environment,
        # False = acc/prod env).
        with self.settings(ALLOWED_HOSTS=['mytestsrv', 'testserver']):
            page = self.template_sans_url.render(Context())
            self.assertEqual(page, "https://mytestsrv")
            page = self.template_with_url.render(Context())
            self.assertEqual(page, "https://mytestsrv/418?I=am&amp;Teapot")

        with self.settings(DEBUG=True):
            page = self.template_sans_url.render(Context())
            self.assertEqual(page, "http://localhost:8000")
            page = self.template_with_url.render(Context())
            self.assertEqual(page, "http://localhost:8000/418?I=am&amp;Teapot")

    def test_domain_fallback_no_allowed_hosts(self):
        # When DEBUG=False and ALLOWED_HOSTS is empty, it should raise an IndexError
        # or handle it gracefully depending on Django's internal behavior for get_current_site.
        # The domain tag itself might fall back to a default or error.
        # For now, let's assume it should error or return a very basic default if any.
        # Django's get_current_site would likely fail if ALLOWED_HOSTS is empty and no Site matches.
        # The tag's fallback is `settings.ALLOWED_HOSTS[0]`.
        with self.settings(DEBUG=False, ALLOWED_HOSTS=[]):
            # This test expects an IndexError because the tag tries to access ALLOWED_HOSTS[0]
            with self.assertRaises(IndexError):
                self.template_sans_url.render(Context({}))

    def test_domain_url_arg_non_ascii(self):
        # Test with a URL argument containing non-ASCII characters.
        # The domain tag itself doesn't explicitly handle URL encoding of the path argument.
        # Django's reverse() or string formatting usually does. Here, it's direct concatenation.
        # Browsers are generally good at handling UTF-8 in paths, but %-encoding is safer.
        # The current tag will output the non-ASCII path as is.
        request = self.request_factory.get('/')
        non_ascii_path = "/उत्तर प्रदेश" # Example: Hindi "Uttar Pradesh"
        template = Template("{% load domain %}{% domain '/उत्तर प्रदेश' %}")
        page = template.render(Context({'request': request}))
        # The '&' will be escaped by default by Django templates if it was part of the path.
        # Here, the path itself is non-ASCII.
        self.assertEqual(page, f"http://mytestsrv{non_ascii_path}")

        # Example with query parameters (which the domain tag doesn't build, but might be part of 'url')
        url_with_query = "/path?city=你好"
        template_query = Template("{% load domain %}{% domain '/path?city=你好' %}")
        page_query = template_query.render(Context({'request': request}))
        # The '&' in query params if it were part of the path would be escaped by default.
        # Here, the non-ASCII chars are in the query string.
        # The domain tag simply appends. Browsers will handle this.
        self.assertEqual(page_query, f"http://mytestsrv{url_with_query.replace('&', '&amp;')}")
