# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe and contributors
# For license information, please see license.txt


import frappe
import json
from frappe.model.document import Document
from frappe.utils import random_string, get_url
from press.utils import get_country_info


class AccountRequest(Document):
	def before_insert(self):
		if not self.team:
			self.team = self.email

		if not self.request_key:
			self.request_key = random_string(32)

		self.ip_address = frappe.local.request_ip
		geo_location = self.get_country_info()
		self.geo_location = json.dumps(geo_location, indent=1, sort_keys=True)
		self.state = geo_location.get("regionName")

		# check for US and EU
		if (
			geo_location.get("country") == "United States"
			or geo_location.get("continent") == "Europe"
		):
			self.is_us_eu = True
		elif self.country == "United States":
			self.is_us_eu = True
		else:
			self.is_us_eu = False

	def after_insert(self):
		if self.send_email:
			self.send_verification_email()

	def get_country_info(self):
		return get_country_info()

	def too_many_requests_with_field(self, field_name, limits):
		key = getattr(self, field_name)
		for allowed_count, kwargs in limits:
			count = frappe.db.count(
				self.doctype,
				{field_name: key, "creation": (">", frappe.utils.add_to_date(None, **kwargs))},
			)
			if count > allowed_count:
				return True
		return False

	@frappe.whitelist()
	def send_verification_email(self):
		url = self.get_verification_url()

		if frappe.conf.developer_mode:
			print(f"\nSetup account URL for {self.email}:")
			print(url)
			print()
			return

		if self.erpnext:
			subject = "Set Up Your ERPNext Account"
			template = "erpnext_verify_account"
		else:
			subject = "Verify your account"
			template = "verify_account"

			if self.invited_by and self.role != "Press Admin":
				subject = f"You are invited by {self.invited_by} to join Frappe Cloud"
				template = "invite_team_member"

		frappe.sendmail(
			recipients=self.email,
			subject=subject,
			template=template,
			args={"link": url, "app": frappe.db.get_value("Saas App", self.saas_app, "title")},
			now=True,
		)

	def get_verification_url(self):
		if self.erpnext:
			return get_url(f"/setup-account?key={self.request_key}")
		elif self.saas:
			# Dumb hardcoded check for frappedesk, remove this later
			if self.saas_app == "frappedesk":
				return get_url(f"/fdesk/setup-account?key={self.request_key}&app={self.saas_app}")
			return get_url(
				f"/{self.saas_app.replace('_', '')}/setup-account?key={self.request_key}&app={self.saas_app}"
			)
		return get_url(f"/dashboard/setup-account/{self.request_key}")

	@property
	def full_name(self):
		return self.first_name + " " + self.last_name
