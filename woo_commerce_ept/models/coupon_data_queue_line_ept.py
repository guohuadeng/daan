import logging, time
from odoo import models, fields, api
from datetime import datetime, timedelta

_logger = logging.getLogger("WooCommerce")


class WooCouponDataQueueLineEpt(models.Model):
    _name = "woo.coupon.data.queue.line.ept"
    _description = "WooCommerce Coupon Data Queue LineEpt"
    _rec_name = "number"

    coupon_data_queue_id = fields.Many2one("woo.coupon.data.queue.ept", ondelete="cascade")
    instance_id = fields.Many2one(related="coupon_data_queue_id.woo_instance_id", copy=False,
                                  help="Coupon imported from this Woocommerce Instance.")
    state = fields.Selection([("draft", "Draft"), ("failed", "Failed"),
                              ("cancelled", "Cancelled"), ("done", "Done")],
                             default="draft", copy=False)
    woo_coupon = fields.Char(string="Woo Coupon Id", help="Id of imported coupon.", copy=False)
    coupon_id = fields.Many2one("woo.coupons.ept", copy=False,
                                    help="coupon created in Odoo.")
    coupon_data = fields.Text(help="Data imported from Woocommerce of current coupon.", copy=False)
    processed_at = fields.Datetime(help="Shows Date and Time, When the data is processed.",
                                   copy=False)
    common_log_lines_ids = fields.One2many("common.log.lines.ept", "woo_coupon_data_queue_line_id",
                                           help="Log lines created against which line.",
                                           string="Log Message")
    number = fields.Char(string='Coupon Name')


    def process_coupon_queue_line(self):
        """
        Process the imported coupon data and create the coupon.
        @author: Nilesh Parmar on Date 31 Dec 2019.
        """
        common_log_book_obj = self.env["common.log.book.ept"]
        start = time.time()
        #below two line add by Haresh Mori on date 7/1/2020, this is used to set is_process_queue as False.
        self.env.cr.execute("""update woo_coupon_data_queue_ept set is_process_queue = False 
        where is_process_queue = True""")
        self._cr.commit()
        queue_id = self.coupon_data_queue_id
        if queue_id.common_log_book_id:
            common_log_book_id = queue_id.common_log_book_id
        else:
            common_log_book_id = common_log_book_obj.create({"type":"import",
                                                             "module":"woocommerce_ept",
                                                             "woo_instance_id":queue_id.woo_instance_id.id,
                                                             "active":True})

        coupons = self.env["woo.coupons.ept"].create_or_write_coupon(self, common_log_book_id)
        if not common_log_book_id.log_lines:
            common_log_book_id.sudo().unlink()
        else:
            queue_id.common_log_book_id = common_log_book_id
        end = time.time()
        _logger.info("Processed %s Coupons in %s seconds." % (str(len(self)), str(end - start)))

    @api.model
    def check_woo_coupon_child_cron(self):
        """
        Cron method which checks if draft order data is there, than make the child cron active.
        @author: Nilesh Parmar on Date 31 Dec 2019.
        """
        child_cron = self.env.ref("woo_commerce_ept.process_woo_coupon_data_queue_child_cron")
        if child_cron and not child_cron.active:
            records = self.search([("state", "=", "draft")], limit=50).ids
            if not records:
                return True
            child_cron.write({"active": True,
                              "nextcall": datetime.now() + timedelta(seconds=10),
                              "numbercall": 1})
        return True

    def auto_coupon_queue_lines_process(self):
        """
            This method used to find a coupon queue line records .
            @author: Nilesh Parmar on Date 31 Dec 2019.
        """
        query = """SELECT coupon_data_queue_id FROM woo_coupon_data_queue_line_ept WHERE state = 
        'draft' ORDER BY "create_date" ASC limit 1;"""
        self._cr.execute(query)
        coupon_queue_data = self._cr.fetchone()
        coupon_queue_id = self.env["woo.coupon.data.queue.ept"].browse(coupon_queue_data)
        coupon_queue_lines = coupon_queue_id and coupon_queue_id.coupon_data_queue_line_ids.filtered(
                lambda x:x.state == "draft")
        coupon_queue_lines and coupon_queue_lines.process_coupon_queue_line()
        return True