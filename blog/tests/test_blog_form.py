from django.test import override_settings, tag

from django_webtest import WebTest

from ..forms import PostForm
from .factories import PostFactory


@tag('forms', 'forms-blog', 'blog')
class PostFormTests(WebTest):
    def test_init(self):
        form = PostForm()
        expected_fields = [
            'title',
            'content',
            'slug',
        ]
        # Verify that the expected fields are part of the form.
        self.assertEqual(set(expected_fields), set(form.fields))

    def test_blank_data(self):
        # Empty form is expected to be invalid.
        form = PostForm({})
        self.assertFalse(form.is_valid())
        expected_errors = {
            'en': ["This field is required."],
            'eo': ["Ĉi tiu kampo estas deviga."],
        }
        for lang in expected_errors:
            with override_settings(LANGUAGE_CODE=lang):
                with self.subTest(LANGUAGE_CODE=lang):
                    self.assertEqual(
                        form.errors,
                        {
                            'title': expected_errors[lang],
                            'content': expected_errors[lang],
                            'slug': expected_errors[lang],
                        }
                    )

    def test_valid_data(self):
        stub = PostFactory.stub(author=None)
        data = {
            'title': stub.title,
            'slug': stub.slug,
            'content': stub.content,
        }
        form = PostForm(data)
        self.assertTrue(form.is_valid())
        saved_post = form.save()
        for field in data:
            with self.subTest(field=field):
                self.assertEqual(getattr(saved_post, field), data[field])
        with self.subTest(field='description'):
            self.assertEqual(saved_post.description, "<p>{}</p>\n".format(stub.description))
        with self.subTest(field='body'):
            self.assertEqual(saved_post.body, "<p>{}</p>\n".format(stub.body))

    def test_submit_existing_slug(self):
        existing_post = PostFactory(author__profile=None)
        data = {
            'title': "Another Title",
            'slug': existing_post.slug, # Use existing slug
            'content': "Some more content."
        }
        form = PostForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('slug', form.errors)
        # Django's default unique validation error message for ModelForms
        # is usually "Post with this Slug already exists."
        # or similar, depending on model's verbose_name.
        # We check for a message containing "already exists" for robustness.
        error_msg = form.errors['slug'][0].lower()
        self.assertIn("slug already exists", error_msg)

    def test_submit_title_too_long(self):
        long_title = "a" * 201 # Post.title max_length is 200
        stub = PostFactory.stub(author=None)
        data = {
            'title': long_title,
            'slug': stub.slug,
            'content': stub.content,
        }
        form = PostForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        # Default max_length error message
        self.assertIn("Ensure this value has at most 200 characters", form.errors['title'][0])

    def test_submit_invalid_slug_chars(self):
        stub = PostFactory.stub(author=None)
        data = {
            'title': stub.title,
            'slug': "invalid slug with spaces and ?", # Invalid slug
            'content': stub.content,
        }
        form = PostForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('slug', form.errors)
        # Default SlugField error message
        self.assertIn("Enter a valid “slug” consisting of letters, numbers, underscores or hyphens.", form.errors['slug'][0])
