# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# Proprietary License. See license.txt


from frappe import _


def get_data():
	return {
		"fieldname": "agent_job",
		"transactions": [{"label": _("Related Documents"), "items": ["Agent Job Step"]}],
	}
