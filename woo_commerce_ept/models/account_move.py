from odoo import models, fields
import requests
from odoo.exceptions import Warning


class AccountMove(models.Model):
    _inherit = "account.move"

    woo_instance_id = fields.Many2one("woo.instance.ept", "Woo Instances")
    is_refund_in_woo = fields.Boolean("Refund In Woo Commerce", default=False)

    def refund_in_woo(self):
        """
        This method is used for refund process. It'll call order refund api for that process
        Note: - It's only generate refund it'll not make any auto transaction according to woo payment method.
              - @param:api_refund: responsible for auto transaction as per woo payment method.
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 23-11-2019.
        :Task id: 156886
        @modify by: Haresh Mori on date 10/12/2019 Modification is removed the create log process and manage to raise warring.
        """
        for refund in self:
            if not refund.woo_instance_id:
                continue
            wcapi = refund.woo_instance_id.woo_connect()
            orders = refund.invoice_line_ids.sale_line_ids.order_id
            for order in orders:
                data = {"amount":str(refund.amount_total), 'reason':str(refund.name or ''),
                        'api_refund':False}
                if refund.woo_instance_id.woo_version == 'v3':
                    response = wcapi.post('orders/%s/refunds' % (order.woo_order_id),
                                          {'order_refund':data})
                else:
                    response = wcapi.post('orders/%s/refunds' % (order.woo_order_id), data)
                if not isinstance(response, requests.models.Response):
                    raise Warning("Refund \n Response is not in proper format :: %s" % (response))
                if response.status_code in [200, 201]:
                    orders and refund.write({'is_refund_in_woo':True})
                else:
                    raise Warning("Refund \n%s" % (response.content))
        return True
