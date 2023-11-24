// Copyright (c) 2023, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on('Ansible Console', {
	onload: function (frm) {
		frappe.ui.keys.add_shortcut({
			shortcut: 'shift+enter',
			action: () => frm.page.btn_primary.trigger('click'),
			page: frm.page,
			description: __('Execute Ansible Command'),
			ignore_inputs: true,
		});
	},
	refresh: function (frm) {
		frm.disable_save();
		frm.page.set_primary_action(__('Execute'), ($btn) => {
			$btn.text(__('Executing...'));
			return frm
				.execute_action('Execute')
				.finally(() => $btn.text(__('Execute')));
		});
	},
});
