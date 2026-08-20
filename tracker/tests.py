from django.test import TestCase, Client
from tracker.models import TrackedEmail, EmailOpen


class TrackerTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.email = TrackedEmail.objects.create(
            recipient="test@example.com",
            subject="Test Subject"
        )

    def test_create_tracked_email_api(self):
        response = self.client.post(
            '/api/emails',
            data={'recipient': 'user@example.com', 'subject': 'Hello'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['recipient'], 'user@example.com')
        self.assertEqual(data['opens'], [])

    def test_gmail_compose_preview_is_ignored(self):
        """
        When pasting the pixel link into Gmail's compose modal,
        the browser sends a request with Referer: https://mail.google.com/.
        This should return 200 OK image but NOT create an EmailOpen record.
        """
        url = f'/track/{self.email.id}.png'
        response = self.client.get(
            url,
            HTTP_REFERER='https://mail.google.com/mail/u/0/#inbox?compose=new'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(EmailOpen.objects.filter(email=self.email).count(), 0)

    def test_head_request_is_ignored(self):
        """HEAD requests during image precheck should return 200 without logging an open."""
        url = f'/track/{self.email.id}.png'
        response = self.client.head(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailOpen.objects.filter(email=self.email).count(), 0)

    def test_valid_recipient_open_is_counted(self):
        """
        When the email is opened by recipient (e.g. via Google Image Proxy or direct client),
        no webmail compose Referer is present. This MUST log an open event.
        """
        url = f'/track/{self.email.id}.png'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailOpen.objects.filter(email=self.email).count(), 1)
        self.assertEqual(self.email.open_count, 1)

    def test_simulate_open_is_counted(self):
        """Simulate Open from dashboard must log an open event."""
        url = f'/track/{self.email.id}.png?cb=123456789'
        response = self.client.get(url, HTTP_REFERER='http://127.0.0.1:8000/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailOpen.objects.filter(email=self.email).count(), 1)

