import frappe
from frappe.core.utils import find
from frappe.utils.password import get_decrypted_password
from press.api.site import overview, protected, get
from press.press.doctype.team.team import Team
from press.api.account import get_account_request_from_key
from press.saas.doctype.saas_app_plan.saas_app_plan import (
	get_app_plan_features,
)
from press.utils import get_current_team

from press.press.doctype.site.saas_site import (
	SaasSite,
	get_saas_domain,
	get_saas_plan,
	get_saas_site_plan,
)
from press.press.doctype.site.saas_pool import get as get_pooled_saas_site
from press.press.doctype.site.erpnext_site import get_erpnext_domain
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
def get_saas_site_and_app():
	"""
	return: Any active saas subscription for team to set it as default for loading dashbaord
	"""
	sub_exists = frappe.db.exists(
		"Saas App Subscription", {"team": get_current_team(), "status": ("!=", "Disabled")}
	)

	if sub_exists:
		return frappe.get_all(
			"Saas App Subscription",
			{"team": get_current_team(), "status": ("!=", "Disabled")},
			["app", "site"],
			limit=1,
		)[0]

	else:
		return {"app": "FrappeCloud", "site": "frappecloud.com"}


@frappe.whitelist()
def get_saas_apps():
	"""
	return: All available saas apps with description and info
	"""
	apps = frappe.get_all(
		"Saas App",
		{"status": "Published"},
		["name", "title", "image", "description", "signup_url"],
	)
	return apps


@frappe.whitelist()
def get_apps():
	"""
	return: All apps created by developer
	"""
	apps = frappe.get_all(
		"Saas App", {"team": get_current_team()}, ["name", "title", "status"]
	)

	for app in apps:
		app["count"] = frappe.db.count(
			"Saas App Subscription", {"status": ("!=", "Disabled"), "app": app.name}
		)

	return apps


@frappe.whitelist()
def get_app(name):
	"""
	return: Fields from saas app
	"""
	app = frappe.get_doc("Saas App", name)

	return app


@frappe.whitelist()
def get_plans(name):
	"""
	return: Saas plans for app
	"""
	plans = frappe.db.get_all(
		"Saas App Plan",
		{"app": name},
		["name", "plan", "site_plan", "enabled"],
		order_by="creation asc",
	)

	for plan in plans:
		features = get_app_plan_features(plan.name)
		plan.features = [{"id": idx, "value": value} for idx, value in enumerate(features)]
		plan.price_usd = frappe.db.get_value("Plan", plan.plan, "price_usd")
		plan.price_inr = frappe.db.get_value("Plan", plan.plan, "price_inr")

	site_plans = frappe.get_all("Plan", {"document_type": "Site"}, pluck="name")

	return {"saas_plans": plans, "site_plans": site_plans}


@frappe.whitelist()
def edit_plan(plan):
	"""
	Edit saas plan and initial plan details
	"""
	# change saas plan fields(site_plan and features)
	plan_doc = frappe.get_doc("Saas App Plan", plan["name"])
	plan_doc.site_plan = plan["site_plan"]
	plan_doc.features = []
	features = [feat["value"] for feat in plan["features"]]
	for feature in features:
		plan_doc.append("features", {"description": feature})
	plan_doc.save(ignore_permissions=True)

	# change initial plan fields(name, prices)
	if plan["plan"] != plan_doc.plan:
		frappe.rename_doc("Plan", plan_doc.plan, plan["plan"])

	frappe.db.set_value("Plan", plan["plan"], "price_usd", plan["price_usd"])
	frappe.db.set_value("Plan", plan["plan"], "price_inr", plan["price_inr"])


@frappe.whitelist()
def create_plan(plan):
	"""
	Create plan
	"""
	# create plan
	plan_doc = frappe.get_doc(
		{
			"doctype": "Plan",
			"plan_name": plan["title"],
			"name": plan["title"],
			"document_type": "Saas App",
			"price_usd": plan["usd"],
			"price_inr": plan["inr"],
		}
	).insert()

	# create saas app plan
	saas_plan_doc = frappe.get_doc(
		{
			"doctype": "Saas App Plan",
			"plan": plan_doc.name,
			"site_plan": plan["site_plan"],
			"app": plan["app"],
			"enabled": 1,
		}
	)

	for feat in plan["features"]:
		saas_plan_doc.append("features", {"description": feat["value"]})

	saas_plan_doc.insert()


@frappe.whitelist()
def get_sites(app):
	sites = frappe.db.sql(
		f"""
		SELECT
			site.name, site.status, subscription.plan, subscription.team
		FROM
			tabSite site
		LEFT JOIN
			`tabSaas App Subscription` subscription
		ON
			site.name = subscription.site
		WHERE
			(subscription.app = '{app}')
	""",
		as_dict=True,
	)
	return sites


@frappe.whitelist()
@protected("Saas App Subscription")
def get_plans_info(name):
	"""
	return: Subscription information for site (plans, active plan, trial)
	"""
	app, site, app_name = frappe.db.get_value(
		"Saas App Subscription", name, ["app", "site", "app_name"]
	)
	saas_app = frappe.get_doc("Saas App", app)
	plans = saas_app.get_plans(site)
	trial_date = frappe.db.get_value("Site", site, "trial_end_date")

	site_data = {
		"plans": plans,
		"trial_end_date": trial_date,
		"site": site,
		"app_name": app_name,
	}

	return site_data


@frappe.whitelist()
def get_subscriptions():
	subscriptions = frappe.get_all(
		"Saas App Subscription",
		{"status": ("!=", "Disabled"), "team": get_current_team()},
		["name", "status", "site", "app_name", "plan"],
	)

	return subscriptions


@frappe.whitelist()
@protected("Saas App Subscription")
def subscription_overview(name):
	subscription = frappe.get_doc("Saas App Subscription", name)
	site_overview = overview(subscription.site)
	site = get(subscription.site)
	return {"subscription": subscription, "site_overview": site_overview, "site": site}


@frappe.whitelist()
@protected("Saas App Subscription")
def change_app_plan(name, new_plan):
	subscription = frappe.get_doc("Saas App Subscription", name)
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
			saas_site.create_subscription(get_saas_site_plan(app))
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
	if subscription:
		subscription.team = team_doc.name
		subscription.save()

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

	frappe.set_user(team_doc.user)
	frappe.local.login_manager.login_as(team_doc.user)

	return site.name


@frappe.whitelist(allow_guest=True)
def get_site_status(key, app=None):
	account_request = get_account_request_from_key(key)
	if not account_request:
		frappe.throw("Invalid or Expired Key")

	domain = get_saas_domain(app) if app else get_erpnext_domain()

	site = frappe.db.get_value(
		"Site",
		{"subdomain": account_request.subdomain, "domain": domain},
		["status", "subdomain"],
		as_dict=1,
	)
	if site:
		return site
	else:
		return {"status": "Pending"}


@frappe.whitelist()
def get_site_url_and_sid(key, app=None):
	account_request = get_account_request_from_key(key)
	if not account_request:
		frappe.throw("Invalid or Expired Key")

	domain = get_saas_domain(app) if app else get_erpnext_domain()

	name = frappe.db.get_value(
		"Site", {"subdomain": account_request.subdomain, "domain": domain}
	)
	site = frappe.get_doc("Site", name)
	return {
		"url": f"https://{site.name}",
		"sid": site.login(),
	}
