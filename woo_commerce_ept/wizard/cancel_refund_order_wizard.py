import requests
from odoo import models, fields, api, _
from odoo.exceptions import Warning, UserError


class woo_cancel_order_wizard(models.TransientModel):
    _name = "woo.cancel.order.wizard"
    _description = "WooCommerce Cancel Order"

    message = fields.Char("Reason")
    journal_id = fields.Many2one('account.journal', 'Journal',
                                 help='You can select here the journal to use for the credit note that will be created. If you leave that field empty, it will use the same journal as the current invoice.')
    auto_create_credit_note = fields.Boolean("Create Credit Note In ERP", default=True,
                                             help="It will create a credit not in Odoo")
    company_id = fields.Many2one("res.company")
    refund_date = fields.Date("Refund Date", default=fields.Date.context_today, required=True)

    def cancel_in_woo(self):
        """
        Cancel Order In Woo using this api we can not cancel partial order
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 23-11-2019.
        :Task id: 156886
        @modify : Haresh Mori on date 10/12/2019, Modification is remove the log create process
        and add the raise warring message
        """
        active_id = self._context.get('active_id')
        order = self.env['sale.order'].browse(active_id)
        instance = order.woo_instance_id

        wcapi = instance.woo_connect()
        info = {'status': 'cancelled'}
        if instance.woo_version == 'v3':
            data = {'order': info}
            response = wcapi.put('orders/%s' % (order.woo_order_id), data)
        else:
            info.update({'id': order.woo_order_id})
            response = wcapi.post('orders/batch', {'update': [info]})
        if not isinstance(response, requests.models.Response):
            raise Warning("Cancel Order \nResponse is not in proper format :: %s" % (response))
        if response.status_code in [200, 201]:
            order.write({'canceled_in_woo': True})
        else:
            raise Warning("Error in Cancel Order %s" % (response.content))
        try:
            result = response.json()
        except Exception as e:
            raise Warning("Json Error : While cancel order %s to WooCommerce for instance %s. \n%s" % (
                    order.woo_order_id, instance.name, e))
        if instance.woo_version == 'v3':
            errors = result.get('errors', '')
            if errors:
                message = errors[0].get('message')
                raise Warning(message)
            else:
                if self.auto_create_credit_note:
                    self.woo_create_credit_note(order)
        else:
            if self.auto_create_credit_note:
                self.woo_create_credit_note(order)
        return True

    def woo_create_credit_note(self, order_id):
        """
        It will create a credit note in Odoo.
        :param order_id:
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 23-11-2019.
        :Task id: 156886
        """
        moves = order_id.invoice_ids.filtered(lambda m: m.type == 'out_invoice' and
                                                        m.invoice_payment_state == 'paid')
        if not moves:
            warning_message = "Order cancel in WooCommerce But unable to create a credit note in Odoo \n" \
                              "Because In Order is not invoice paid."
            raise Warning(warning_message)
        default_values_list = []
        for move in moves:
            default_values_list.append({
                'ref': _('Reversal of: %s, %s') % (move.name, self.message) if self.message else _(
                    'Reversal of: %s') % (move.name),
                'date': self.refund_date or move.date,
                'invoice_date': move.is_invoice(include_receipts=True) and (
                        self.refund_date or move.date) or False,
                'journal_id': self.journal_id and self.journal_id.id or move.journal_id.id,
                'invoice_payment_term_id': None,
                'auto_post': True if self.refund_date > fields.Date.context_today(self) else False,
            })
        moves._reverse_moves(default_values_list)
        return True
