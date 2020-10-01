from odoo import models, fields, api
import logging

_logger = logging.getLogger("WooCommerce")


class WooProductDataQueueEpt(models.Model):
    _name = 'woo.product.data.queue.ept'
    _description = "WooCommerce Products Synced Queue Process"
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', copy=False)
    woo_skip_existing_products = fields.Boolean("Do not Update Existing Product")
    woo_instance_id = fields.Many2one("woo.instance.ept", string="Instances")
    state = fields.Selection([('draft', 'Draft'), ('partial', 'Partially Done'),
                              ("failed", "Failed"), ('done', 'Done')], default='draft',
                             compute="_compute_state", store=True)
    queue_line_ids = fields.One2many('woo.product.data.queue.line.ept', 'queue_id')
    log_book_id = fields.Many2one('common.log.book.ept', string="Log Book Id")
    common_log_lines_ids = fields.One2many(related="log_book_id.log_lines")
    products_count = fields.Integer(compute='_compute_lines')
    product_draft_state_count = fields.Integer(compute='_compute_lines')
    product_done_state_count = fields.Integer(compute='_compute_lines')
    product_failed_state_count = fields.Integer(compute='_compute_lines')
    cancelled_line_count = fields.Integer(compute='_compute_lines')
    created_by = fields.Selection([("import", "By Import Process"), ("webhook", "By Webhook")],
                                  help="Identify the process that generated a queue.", default="import")
    is_process_queue = fields.Boolean('Is Processing Queue', default=False)
    running_status = fields.Char(default="Running...")
    queue_process_count = fields.Integer(string="Queue Process Times",
                                         help="it is used know queue how many time processed")
    is_action_require = fields.Boolean(default=False,
                                       help="it is used to find the action require queue")

    @api.depends("queue_line_ids.state")
    def _compute_lines(self):
        """
        Computes product queue lines by different states.
        @author: Maulik Barad on Date 25-Dec-2019.
        """
        for record in self:
            queue_lines = record.queue_line_ids
            record.products_count = len(queue_lines)
            record.product_draft_state_count = len(queue_lines.filtered(lambda x: x.state == "draft"))
            record.product_done_state_count = len(queue_lines.filtered(lambda x: x.state == "done"))
            record.product_failed_state_count = len(queue_lines.filtered(lambda x: x.state == "failed"))
            record.cancelled_line_count = len(queue_lines.filtered(lambda x: x.state == "cancelled"))

    @api.depends("queue_line_ids.state")
    def _compute_state(self):
        """
        Computes state of Product queue from queue lines' state.
        @author: Maulik Barad on Date 25-Dec-2019.
        """
        for record in self:
            if (record.product_done_state_count + record.cancelled_line_count) == record.products_count:
                record.state = "done"
            elif record.product_draft_state_count == record.products_count:
                record.state = "draft"
            elif record.product_failed_state_count == record.products_count:
                record.state = "failed"
            else:
                record.state = "partial"

    @api.model
    def create(self, vals):
        """
        Inherited and create a sequence and new product queue
        :param vals: It will contain the updated data and its type is Dictionary
        :return: It will return the object of newly created product queue
        """
        record_name = "/"
        sequence_id = self.env.ref("woo_commerce_ept.ir_sequence_product_data_queue").id
        if sequence_id:
            record_name = self.env['ir.sequence'].browse(sequence_id).next_by_id()
        vals.update({"name": record_name})
        return super(WooProductDataQueueEpt, self).create(vals)

    def action_force_done(self):
        """
        Cancels all draft and failed queue lines.
        @author: Maulik Barad on Date 25-Dec-2019. 
        """
        need_to_cancel_queue_lines = self.queue_line_ids.filtered(lambda x: x.state in ["draft", "failed"])
        need_to_cancel_queue_lines.write({"state": "cancelled"})
        return True

    def create_product_queue_from_webhook(self, product_data, instance, wcapi):
        """
        This method used to create a product queue from webhook response.
        @author: Haresh Mori on Date 31-Dec-2019.
        """
        if product_data.get("type") == "variable":
            params = {"per_page": 100}
            response = wcapi.get("products/%s/variations" % (product_data.get("id")), params=params)
            variants_data = response.json()

            total_pages = response.headers.get("X-WP-TotalPages")
            if int(total_pages) > 1:
                for page in range(2, int(total_pages) + 1):
                    params["page"] = page
                    response = wcapi.get("products/%s/variations" % (product_data.get("id")), params=params)
                    variants_data += response.json()

            if isinstance(variants_data, list):
                product_data.update({"variations": variants_data})

        import_export = self.env["woo.process.import.export"].create(
            {"woo_instance_id": instance.id})
        product_data_queue = import_export.sudo().woo_import_products([product_data], "webhook")
        _logger.info(
            "Imported product {0} of {1} via Webhook Successfully.".format(product_data.get("id"),
                                                                           instance.name))

        product_data_queue.queue_line_ids.sync_woo_product_data()
        _logger.info(
            "Processed product {0} of {1} via Webhook Successfully.".format(product_data.get("id"),
                                                                            instance.name))
