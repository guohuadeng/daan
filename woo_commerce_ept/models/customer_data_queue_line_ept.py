import json, logging, time
from datetime import datetime, timedelta
from odoo import models, fields

_logger = logging.getLogger("Woo")


class WooCustomerDataQueueLineEpt(models.Model):
    _name = "woo.customer.data.queue.line.ept"
    _description = 'WooCommerce Sync Customer Queue Line Data'
    _rec_name = "woo_synced_data_id"
    woo_instance_id = fields.Many2one('woo.instance.ept', string='Instance',
                                      help="Determines that queue line associated with particular instance")
    state = fields.Selection([('draft', 'Draft'), ('failed', 'Failed'), ("cancelled", "Cancelled"),
                              ('done', 'Done')], default='draft')
    last_process_date = fields.Datetime(readonly=True)
    woo_synced_data = fields.Char(string='WooCommerce Synced Data')
    woo_synced_data_id = fields.Char(string='Woo Customer Id')
    queue_id = fields.Many2one('woo.customer.data.queue.ept')
    common_log_lines_ids = fields.One2many("common.log.lines.ept",
                                           "woo_customer_data_queue_line_id",
                                           help="Log lines created against which line.")
    name = fields.Char(string="Customer", help="Customer Name of Woo Commerce")

    def woo_customer_data_queue_to_odoo(self):
        """
        Call method according to execution of child cron which is responsible to add customer.
        :return: boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 30-10-2019.
        :Task id: 156886
        """
        common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "res.partner"
        model_id = common_log_line_obj.get_model_id(model)
        log_lines_id = []
        # below two line add by Haresh Mori on date 7/1/2020, this is used to set is_process_queue as False.
        self.env.cr.execute("""update woo_customer_data_queue_ept set is_process_queue = False 
        where is_process_queue = True""")
        self._cr.commit()
        start = time.time()
        queue_lines = self
        if self._context.get('line_ids', False):
            queue_lines = self._context.get('line_ids')
        elif not self:
            query = """select queue.id
                from woo_customer_data_queue_line_ept as queue_line
                inner join woo_customer_data_queue_ept as queue on queue_line.queue_id = queue.id
                where queue_line.state='draft' and queue.is_action_require = 'False'
                ORDER BY queue_line.create_date ASC limit 1"""
            self._cr.execute(query)
            order_queue_data = self._cr.fetchone()
            customer_queue = self.env["woo.customer.data.queue.ept"].browse(order_queue_data)
            if not customer_queue:
                return
            queue_lines = customer_queue.queue_line_ids
            customer_queue.queue_process_count += 1
            if customer_queue.queue_process_count > 3:
                customer_queue.is_action_require = True
                note = "<p>Attention %s queue is processed 3 times you need to process it manually.</p>" % (customer_queue.name)
                customer_queue.message_post(body=note)
                if customer_queue.woo_instance_id.is_create_schedule_activity:
                    model = self.env['ir.model'].search([('model', '=', 'woo.customer.data.queue.ept')])
                    common_log_obj.create_woo_schedule_activity(customer_queue, model, True)
                return
            self._cr.commit()

            # queue_lines = self.search([('state', '=', 'draft')], limit=100)
        partner_obj = self.env['res.partner']
        # Add by Haresh Mori on date 7/1/2020, Add commit after 10 customer record process and
        # also manage which queue is running in the background.
        commit_count = 0
        for customer_queue_line in queue_lines:
            commit_count += 1
            if commit_count == 10:
                customer_queue_line.queue_id.is_process_queue = True
                self._cr.commit()
                commit_count = 0
            instance = customer_queue_line.woo_instance_id
            if instance.woo_version == 'v3':
                billing = "billing_address"
                shipping = "shipping_address"
            else:
                billing = "billing"
                shipping = "shipping"
            customer_val = json.loads(customer_queue_line.woo_synced_data)
            woo_customer_id = customer_val.get('id', False)
            partner = customer_val.get(billing, False) and partner_obj.woo_create_or_update_customer(
                woo_customer_id,
                customer_val.get(billing),
                True,
                False,
                False,
                instance
            )
            if partner:
                parent_id = partner.id
                if partner.parent_id:
                    parent_id = partner.parent_id.id
                customer_val.get(shipping, False) and partner_obj.woo_create_or_update_customer(
                    False,
                    customer_val.get(shipping),
                    False,
                    parent_id,
                    'delivery',
                    instance,
                )
                customer_queue_line.write({'state': 'done', 'last_process_date': datetime.now()})
            else:
                customer_queue_line.write({'state': 'failed', 'last_process_date': datetime.now()})
                log_id = common_log_line_obj.create({
                    'model_id': model_id,
                    'message': "Please check customer name or addresses in WooCommerce.",
                    'woo_customer_data_queue_line_id': customer_queue_line.id
                })
                log_lines_id.append(log_id.id)
            customer_queue_line.queue_id.is_process_queue = False

        queues = queue_lines.queue_id
        for queue in queues:
            q_dict = {}
            q_line = queue.queue_line_ids
            log_lines = common_log_line_obj.search([
                ('woo_customer_data_queue_line_id', 'in', q_line.mapped('id')),
                ('log_line_id', '=', False)
            ]) if log_lines_id else False
            if log_lines:
                if queue.common_log_book_id:
                    queue.common_log_book_id.write({'log_lines': [(6, 0, log_lines.ids)]})
                else:
                    common_log_id = common_log_obj.create({
                        'type': 'import',
                        'module': 'woocommerce_ept',
                        'woo_instance_id': instance.id,
                        'active': True,
                        'log_lines': [(6, 0, log_lines.ids)]
                    })
                    q_dict.update({'common_log_book_id': common_log_id.id})
            queue.write(q_dict)
        end = time.time()
        _logger.info("Processed %s Customers in %s seconds." % (str(len(queue_lines)), str(end - start)))
        return True

    def create_customer_queue_schedule_activity(self, queue_id):
        """
            this method is used to create a schedule activity for queue.
            @:parameter : queue_id : it is object of queue
            Author: Nilesh Parmar
            Date: 13 february 2020.
            :return:
        """
        mail_activity_obj = self.env["mail.activity"]
        model_id = self.env["ir.model"].search([("model", "=", "woo.customer.data.queue.ept")])
        activity_type_id = queue_id.woo_instance_id.activity_type_id.id
        date_deadline = datetime.strftime(datetime.now() + timedelta(
            days=queue_id.woo_instance_id.date_deadline), "%Y-%m-%d")
        if queue_id:
            note = "Attention %s queue is processed 3 times you need to process it manually" % (queue_id.name)
            for user_id in queue_id.woo_instance_id.user_ids:
                mail_activity = mail_activity_obj.search([("res_model_id", "=", model_id.id),
                                                          ("user_id", "=", user_id.id),
                                                          ("res_name", "=", queue_id.name),
                                                          ("activity_type_id", "=", activity_type_id)])
                if not mail_activity:
                    vals = {"activity_type_id": activity_type_id,
                            "note": note,
                            "res_id": queue_id.id,
                            "user_id": user_id.id,
                            "res_model_id": model_id.id,
                            "date_deadline": date_deadline}
                    try:
                        mail_activity_obj.create(vals)
                    except:
                        _logger.info("Unable to create schedule activity, Please give proper "
                                     "access right of this user :%s  " % (user_id.name))
        return True

    def woo_customer_process_child_cron(self):
        """
        Parent cron which is responsible to execute child cron
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 30-10-2019.
        :Task id: 156886
        """
        child_cron_of_process = self.env.ref('woo_commerce_ept.ir_cron_child_woo_customer_data_into_odoo')
        if child_cron_of_process and not child_cron_of_process.active:
            results = self.search([('state', '=', 'draft')], limit=100)
            if not results:
                return True
            child_cron_of_process.write({
                'active': True,
                'numbercall': 1,
                'nextcall': datetime.now() + timedelta(seconds=10)
            })
        return True
