# Copyright (c) 2023, Frappe and Contributors
# See license.txt

from unittest.mock import MagicMock, patch, Mock
import frappe
from frappe.tests.utils import FrappeTestCase
from press.press.doctype.alertmanager_webhook_log.test_alertmanager_webhook_log import (
	create_test_alertmanager_webhook_log,
)
from press.press.doctype.site.test_site import create_test_site
from press.utils.test import foreground_enqueue_doc


from press.press.doctype.team.test_team import create_test_press_admin_team


class MockTwilioClient:
	def __init__(self, account_sid, auth_token):  # noqa
		pass

	@property
	def calls(self):
		return frappe._dict({"create": self.create_call})

	def create_call(self, **kwargs):
		return MagicMock()


@patch("press.press.doctype.incident.incident.frappe.db.commit", new=Mock())
class TestIncident(FrappeTestCase):
	def setUp(self):
		frappe.db.set_value("Press Settings", None, "twilio_account_sid", "test")
		frappe.db.set_value("Press Settings", None, "twilio_auth_token", "test")
		frappe.db.set_value("Press Settings", None, "twilio_phone_number", "test")

		self._create_test_incident_settings()

	def tearDown(self):
		frappe.db.rollback()

	def _create_test_incident_settings(self):
		user1 = create_test_press_admin_team().user
		user2 = create_test_press_admin_team().user
		self.test_phno_1 = "+911234567890"
		self.test_phno_2 = "+911234567891"
		frappe.get_doc(
			{
				"doctype": "Incident Settings",
				"users": [
					{
						"user": user1,
						"phone": self.test_phno_1,
					},
					{
						"user": user2,
						"phone": self.test_phno_2,
					},
				],
			}
		).insert()

	@patch(
		"press.press.doctype.incident.incident.frappe.enqueue_doc", new=foreground_enqueue_doc
	)
	@patch("press.press.doctype.incident.incident.Incident.wait_for_pickup", new=Mock())
	@patch.object(MockTwilioClient, "create_call")
	@patch("press.press.doctype.incident.incident.Client", new=MockTwilioClient)
	def test_incident_creation_places_phone_call_to_all_humans_in_incident_team_if_no_one_picks_up(
		self, mock_calls_create: Mock
	):
		frappe.get_doc(
			{
				"doctype": "Incident",
				"alertname": "Test Alert",
			}
		).insert()
		self.assertEqual(mock_calls_create.call_count, 2)
		mock_calls_create.assert_any_call(
			from_="test",
			to=self.test_phno_1,
			url="http://demo.twilio.com/docs/voice.xml",
		)
		mock_calls_create.assert_any_call(
			from_="test",
			to=self.test_phno_2,
			url="http://demo.twilio.com/docs/voice.xml",
		)

	def test_incident_creation_calls_only_one_person_if_first_person_picks_up(self):
		pass

	@patch("press.press.doctype.incident.incident.Incident.wait_for_pickup", new=Mock())
	@patch.object(MockTwilioClient, "create_call", new=Mock())
	@patch("press.press.doctype.incident.incident.Client", new=MockTwilioClient)
	def test_incident_gets_created_on_alert_that_meets_conditions(self):
		incident_count = frappe.db.count("Incident")
		create_test_alertmanager_webhook_log()
		self.assertEqual(frappe.db.count("Incident") - incident_count, 1)

	def test_incident_not_created_when_sites_very_less_than_scope_is_down(self):
		"""1 out of 3 sites on server down"""
		incident_count_before = frappe.db.count("Incident")
		site = create_test_site()
		create_test_site(server=site.server)
		create_test_site(server=site.server)
		create_test_alertmanager_webhook_log(site=site)
		self.assertEqual(frappe.db.count("Incident"), incident_count_before)

	def test_incident_created_when_sites_within_scope_is_down(self):
		"""3 out of 3 sites on server down"""
		incident_count_before = frappe.db.count("Incident")
		site = create_test_site()
		site2 = create_test_site(server=site.server)
		site3 = create_test_site(server=site.server)
		create_test_alertmanager_webhook_log(site=site)
		create_test_alertmanager_webhook_log(site=site2)
		create_test_alertmanager_webhook_log(site=site3)
		self.assertEqual(frappe.db.count("Incident") - incident_count_before, 1)
