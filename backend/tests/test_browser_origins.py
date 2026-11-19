"""Browser Origin headers must be tested, not just cookies and CSRF tokens."""
import unittest
from unittest.mock import patch
from django.test import Client, SimpleTestCase, override_settings
from backend.tests.drf_client import RailwayAPIClient

@override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173', 'http://localhost:5173'])
class BrowserOriginTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get('/api/csrf').json()['csrfToken']

    def post(self, origin, path='/api/logout', token=True):
        return self.client.post(path, data={}, content_type='application/json',
            HTTP_HOST='127.0.0.1:8000', HTTP_ORIGIN=origin,
            HTTP_X_CSRFTOKEN=self.token if token else '')

    def test_vite_origins_can_submit_with_valid_csrf(self):
        for origin in ['http://127.0.0.1:5173', 'http://localhost:5173']:
            self.assertEqual(self.post(origin).status_code, 200)

    def test_untrusted_origin_is_rejected_even_with_valid_token(self):
        self.assertEqual(self.post('http://untrusted.example').status_code, 403)

    def test_trusted_origin_still_requires_token(self):
        self.assertEqual(self.post('http://127.0.0.1:5173', token=False).status_code, 403)

    def test_registration_reaches_validation_from_vite(self):
        response = self.post('http://127.0.0.1:5173', '/api/register')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Full name is required.')
