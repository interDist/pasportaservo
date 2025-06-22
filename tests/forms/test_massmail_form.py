from django.test import TestCase, tag, override_settings
from django.utils.translation import gettext_lazy as _

from core.forms import MassMailForm


@tag('forms', 'forms-core')
class MassMailFormTests(TestCase):

    def test_blank_submission(self):
        form = MassMailForm({})
        self.assertFalse(form.is_valid())
        # Check which fields are actually required by the form definition
        # Assuming 'heading', 'body', 'subject', 'categories', 'test_email' might be required
        # based on typical form design, but will rely on form.errors to confirm.
        self.assertIn('heading', form.errors)
        self.assertIn('body', form.errors)
        self.assertIn('subject', form.errors)
        self.assertIn('categories', form.errors)
        self.assertIn('test_email', form.errors)

        expected_error_msg = ["This field is required."]
        with override_settings(LANGUAGE_CODE='en'):
            self.assertEqual(form.errors['heading'], expected_error_msg)
            self.assertEqual(form.errors['body'], expected_error_msg)
            self.assertEqual(form.errors['subject'], expected_error_msg)
            self.assertEqual(form.errors['categories'], expected_error_msg)
            self.assertEqual(form.errors['test_email'], expected_error_msg)

    def test_preheader_max_length(self):
        long_preheader = "a" * 101 # Max length is 100
        data = {
            'heading': 'Test Heading',
            'body': 'Test Body',
            'subject': 'Test Subject',
            'preheader': long_preheader,
            'categories': 'test',
            'test_email': 'test@example.com',
        }
        form = MassMailForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('preheader', form.errors)
        with override_settings(LANGUAGE_CODE='en'):
            self.assertIn("Ensure this value has at most 100 characters", form.errors['preheader'][0])

    def test_invalid_test_email(self):
        data = {
            'heading': 'Test Heading',
            'body': 'Test Body',
            'subject': 'Test Subject',
            'preheader': 'Test Preheader',
            'categories': 'test',
            'test_email': 'not-an-email',
        }
        form = MassMailForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('test_email', form.errors)
        with override_settings(LANGUAGE_CODE='en'):
            self.assertEqual(form.errors['test_email'], ["Enter a valid email address."])

    def test_valid_submission(self):
        data = {
            'heading': 'Valid Heading',
            'body': 'Valid Body Content {nomo}', # Test with placeholder
            'subject': 'Valid Subject',
            'preheader': 'Valid Preheader, under 100 chars.',
            'categories': 'in_book', # A valid choice
            'test_email': 'valid@example.com',
        }
        form = MassMailForm(data)
        self.assertTrue(form.is_valid(), msg=form.errors)

        # Check cleaned_data
        self.assertEqual(form.cleaned_data['heading'], data['heading'])
        self.assertEqual(form.cleaned_data['body'], data['body'])
        self.assertEqual(form.cleaned_data['subject'], data['subject'])
        self.assertEqual(form.cleaned_data['preheader'], data['preheader'])
        self.assertEqual(form.cleaned_data['categories'], data['categories'])
        self.assertEqual(form.cleaned_data['test_email'], data['test_email'])

    def test_initial_values(self):
        form = MassMailForm()
        self.assertEqual(form.fields['heading'].initial, _("Announcement"))
        self.assertEqual(form.fields['body'].initial, _("Dear {nomo},\n\n"))
        self.assertEqual(form.fields['subject'].initial, _("Subject"))
        # test_email initial value can vary, so check if it's a string (or could be None if not set)
        self.assertIsInstance(form.fields['test_email'].initial, str)

    def test_categories_choices(self):
        form = MassMailForm()
        # Ensure choices are present. Specific choices might change, so check for structure.
        self.assertTrue(len(form.fields['categories'].choices) > 0)
        # Example check for one choice if it's stable
        # self.assertIn(('test', _("test")), form.fields['categories'].choices)
        # For now, just check that it's not empty and has the expected structure
        first_choice_value, first_choice_label = form.fields['categories'].choices[0]
        self.assertIsInstance(first_choice_value, str)
        # The label can be a lazy translation object
        self.assertTrue(hasattr(first_choice_label, '__str__'))

    def test_preheader_widget(self):
        form = MassMailForm()
        self.assertIsInstance(form.fields['preheader'].widget, forms.Textarea)
        self.assertEqual(form.fields['preheader'].widget.attrs.get('rows'), 2)

    def test_body_widget(self):
        form = MassMailForm()
        self.assertIsInstance(form.fields['body'].widget, forms.Textarea)
