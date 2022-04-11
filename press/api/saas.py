import frappe
from frappe.core.utils import find
from frappe.utils.password import get_decrypted_password
from press.press.doctype.team.team import Team
from press.api.account import get_account_request_from_key
from press.utils import get_current_team

from press.press.doctype.site.saas_site import SaasSite, get_saas_domain, get_saas_plan
from press.press.doctype.site.saas_pool import get as get_pooled_saas_site
from press.utils.billing import get_erpnext_com_connection


@frappe.whitelist()
def get_saas_subscriptions_for_team():
	"""
	return: Active saas subscriptions for team
	"""
	team = get_current_team()
	image_paths = {
		app.app: app.image for app in frappe.get_all("Saas App", fields=["app", "image"])
	}

	subscriptions = frappe.get_all(
		"Saas App Subscription",
		filters={"team": team, "status": ("!=", "Disabled")},
		fields=["name", "plan", "site", "app", "app_name"],
	)

	for sub in subscriptions:
		sub["image_path"] = image_paths[sub["app"]]

	return subscriptions


@frappe.whitelist()
def get_saas_site_and_app(team):
	"""
	return: Any active saas subscription for team to set it as default for loading dashbaord
	"""
	data = frappe.get_all(
		"Saas App Subscription", {"team": team}, ["app", "site"], limit=1
	)[0]

	return data


@frappe.whitelist()
def get_app_image_path(app):
	return frappe.db.get_value("Saas App", app, "image")


@frappe.whitelist()
def get_site_sub_info(site, app):
	"""
	return: Subscription information for site (plans, active plan, trial)
	"""
	saas_app = frappe.get_doc("Saas App", app)
	plans = saas_app.get_plans(site)
	trial_date = frappe.db.get_value("Site", site, "trial_end_date")

	site_data = {"plans": plans, "trial_end_date": trial_date}

	return site_data


@frappe.whitelist()
def change_app_plan(site, app, new_plan):
	subscription_name = frappe.get_all(
		"Saas App Subscription",
		filters={"site": site, "app": app["app"], "status": ("!=", "Disabled")},
		pluck="name",
	)
	subscription = frappe.get_doc("Saas App Subscription", subscription_name[0])
	subscription.change_plan(new_plan)


# ----------------------------- SIGNUP APIs ---------------------------------


@frappe.whitelist(allow_guest=True)
def account_request(
	subdomain,
	email,
	password,
	first_name,
	last_name,
	phone_number,
	country,
	app,
	url_args=None,
):
	email = email.strip().lower()
	frappe.utils.validate_email_address(email, True)

	if not check_subdomain_availability(subdomain, app):
		frappe.throw(f"Subdomain {subdomain} is already taken")

	all_countries = frappe.db.get_all("Country", pluck="name")
	country = find(all_countries, lambda x: x.lower() == country.lower())
	if not country:
		frappe.throw("Country filed should be a valid country name")

	account_request = frappe.get_doc(
		{
			"doctype": "Account Request",
			"saas": True,
			"saas_app": app,
			"erpnext": False,
			"subdomain": subdomain,
			"email": email,
			"password": password,
			"role": "Press Admin",
			"first_name": first_name,
			"last_name": last_name,
			"phone_number": phone_number,
			"country": country,
			"url_args": url_args,
		}
	).insert(ignore_permissions=True)

	current_user = frappe.session.user
	current_session_data = frappe.session.data
	frappe.set_user("Administrator")

	try:
		pooled_site = get_pooled_saas_site(app)
		if pooled_site:
			# Rename a standby site
			SaasSite(site=pooled_site, app=app).rename_pooled_site(account_request)
		else:
			# Create a new site if pooled sites aren't available
			saas_site = SaasSite(account_request=account_request, app=app).insert(
				ignore_permissions=True
			)
			saas_site.create_subscription(get_saas_plan(app))
	finally:
		frappe.set_user(current_user)
		frappe.session.data = current_session_data


@frappe.whitelist(allow_guest=True)
def check_subdomain_availability(subdomain, app):
	# Only for ERPNext domains

	erpnext_com = get_erpnext_com_connection()
	result = erpnext_com.post_api(
		"central.www.signup.check_subdomain_availability", {"subdomain": subdomain}
	)
	if result:
		return False

	exists = bool(
		frappe.db.exists(
			"Site",
			{
				"subdomain": subdomain,
				"domain": get_saas_domain(app),
				"status": ("!=", "Archived"),
			},
		)
	)
	if exists:
		return False

	return True


@frappe.whitelist(allow_guest=True)
def setup_account(key, business_data=None):
	account_request = get_account_request_from_key(key)
	if not account_request:
		frappe.throw("Invalid or Expired Key")

	frappe.set_user("Administrator")

	if business_data:
		business_data = frappe.parse_json(business_data)

	if isinstance(business_data, dict):
		business_data = {
			key: business_data.get(key)
			for key in [
				"company",
				"no_of_employees",
				"industry",
				"no_of_users",
				"designation",
				"referral_source",
				"agreed_to_partner_consent",
			]
		}

	account_request.update(business_data)
	account_request.save(ignore_permissions=True)

	create_team_from_account_request(account_request)


@frappe.whitelist(allow_guest=True)
def headless_setup_account(key):
	"""
	Ignores the data collection step in setup-account.html
	"""
	account_request = get_account_request_from_key(key)
	if not account_request:
		frappe.throw("Invalid or Expired Key")

	frappe.set_user("Administrator")

	create_team_from_account_request(account_request)


def create_team_from_account_request(account_request):
	email = account_request.email

	if not frappe.db.exists("Team", email):
		team_doc = Team.create_new(
			account_request,
			account_request.first_name,
			account_request.last_name,
			password=get_decrypted_password("Account Request", account_request.name, "password"),
			country=account_request.country,
			via_erpnext=True,
		)
	else:
		team_doc = frappe.get_doc("Team", email)

	site_name = frappe.db.get_value("Site", {"account_request": account_request.name})
	site = frappe.get_doc("Site", site_name)
	site.team = team_doc.name
	site.save()

	subscription = site.subscription

	plan = frappe.get_all(
		"Saas App Plan",
		filters={"plan": get_saas_plan(account_request.saas_app)},
		pluck="name",
	)[0]

	frappe.get_doc(
		{
			"doctype": "Saas App Subscription",
			"team": team_doc.name,
			"app": account_request.saas_app,
			"site": site_name,
			"saas_app_plan": plan,
		}
	).insert(ignore_permissions=True)

	if subscription:
		subscription.team = team_doc.name
		subscription.save()

	frappe.set_user(team_doc.user)
	frappe.local.login_manager.login_as(team_doc.user)

	return site.name
