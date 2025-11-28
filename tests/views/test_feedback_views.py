from unittest.mock import patch

from django.urls import reverse

from django_webtest import WebTest

from core.models import FEEDBACK_TYPES
from tests.assertions import AdditionalAsserts
from tests.utils import UserMixin


@patch('core.views.GQLClient')
class FeedbackViewTest(UserMixin, WebTest, AdditionalAsserts):
    def setUp(self):
        super().setUp()
        self.feedback_type = next(iter(FEEDBACK_TYPES.keys()))
        self.feedback_url = reverse('feedback')
        self.feedback_url_eo = reverse('feedback', locale='eo')

    def test_get_not_allowed(self, mock_gql_client):
        """
        Tests that GET requests to the feedback view are not allowed.
        """
        response = self.app.get(self.feedback_url, expect_errors=True)
        self.assertEqual(response.status_code, 405)

    def test_post_unauthenticated_private(self, mock_gql_client):
        """
        Tests that an unauthenticated user can submit private feedback.
        """
        with self.assertLogs('django.core.mail', level='INFO') as cm:
            response = self.app.post(
                self.feedback_url,
                {
                    'feedback_on': self.feedback_type,
                    'message': 'This is a test feedback message.',
                    'private': 'on',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        self.assertEqual(len(cm.records), 1)
        self.assertIn(f'Feedback on {FEEDBACK_TYPES[self.feedback_type].name}.', cm.output[0])
        self.assertIn('This is a test feedback message.', cm.output[0])

    def test_post_unauthenticated_public(self, mock_gql_client):
        """
        Tests that an unauthenticated user can submit public feedback.
        """
        mock_gql_client.return_value.execute.return_value = {
            'addDiscussionComment': {'comment': {'id': '12345'}}
        }
        response = self.app.post(
            self.feedback_url,
            {
                'feedback_on': self.feedback_type,
                'message': 'This is a public test feedback message.',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        mock_gql_client.return_value.execute.assert_called_once()

    def test_post_authenticated_private(self, mock_gql_client):
        """
        Tests that an authenticated user can submit private feedback.
        """
        self.login()
        with self.assertLogs('django.core.mail', level='INFO') as cm:
            response = self.app.post(
                self.feedback_url,
                {
                    'feedback_on': self.feedback_type,
                    'message': 'This is a test feedback message from a logged in user.',
                    'private': 'on',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        self.assertEqual(len(cm.records), 1)
        self.assertIn(f'User {self.user.pk} ({self.user.username}):', cm.output[0])
        self.assertIn('This is a test feedback message from a logged in user.', cm.output[0])

    def test_post_authenticated_public(self, mock_gql_client):
        """
        Tests that an authenticated user can submit public feedback.
        """
        self.login()
        mock_gql_client.return_value.execute.return_value = {
            'addDiscussionComment': {'comment': {'id': '12345'}}
        }
        response = self.app.post(
            self.feedback_url,
            {
                'feedback_on': self.feedback_type,
                'message': 'This is a public test feedback message from a logged in user.',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        mock_gql_client.return_value.execute.assert_called_once()

    def test_post_invalid_form(self, mock_gql_client):
        """
        Tests that an invalid form submission is handled correctly and that the
        message is truncated in the log.
        """
        long_message = 'a' * 2000
        with self.assertLogs('PasportaServo.ui.feedback', level='ERROR') as cm:
            response = self.app.post(
                self.feedback_url,
                {'feedback_on': 'invalid_type', 'message': long_message},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_form_fail.html')
        self.assertEqual(len(cm.records), 1)
        self.assertIn('Feedback form did not validate correctly', cm.output[0])
        self.assertIn(f'Original submission: #{long_message[:1000]}#', cm.output[0])

    def test_post_invalid_form_ajax(self, mock_gql_client):
        """
        Tests that an invalid form submission is handled correctly for an AJAX request.
        """
        response = self.app.post(
            self.feedback_url,
            {'feedback_on': 'invalid_type', 'message': 'test'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'result': False})

    def test_post_public_gql_error(self, mock_gql_client):
        """
        Tests that a GQL error during public submission results in a private submission.
        """
        mock_gql_client.return_value.execute.side_effect = Exception('GQL Error')
        with self.assertLogs('django.core.mail', level='INFO') as cm:
            response = self.app.post(
                self.feedback_url,
                {
                    'feedback_on': self.feedback_type,
                    'message': 'This is a public test feedback message.',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        self.assertEqual(len(cm.records), 1)
        self.assertIn('During public submission, an exception has occured.', cm.output[0])

    def test_language_eo(self, mock_gql_client):
        """
        Tests that the feedback view works correctly with the 'eo' language code.
        """
        with self.assertLogs('django.core.mail', level='INFO') as cm:
            response = self.app.post(
                self.feedback_url_eo,
                {
                    'feedback_on': self.feedback_type,
                    'message': 'This is a test feedback message in Esperanto.',
                    'private': 'on',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/feedback_sent.html')
        self.assertContains(response, 'Via komento estis registrita sukcese. Dankon!')
        self.assertEqual(len(cm.records), 1)
        self.assertIn(f'Feedback on {FEEDBACK_TYPES[self.feedback_type].esperanto_name}.', cm.output[0])
        self.assertIn('This is a test feedback message in Esperanto.', cm.output[0])
