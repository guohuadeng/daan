# -*- coding: utf-8 -*-
"""
Main Controller.
"""
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger("Woo")


class Webhook(http.Controller):
    """
    Controller for Webhooks.
    @author: Maulik Barad on Date 09-Jan-2019.
    """

    @http.route("/create_order_webhook_odoo", csrf=False, auth="public", type="json")
    def create_order_webhook(self):
        """
        Route for handling the order creation webhook of WooCommerce.
        @author: Maulik Barad on Date 21-Dec-2019.
        """
        res, instance = self.get_basic_info()

        if instance.active and res.get("status") in instance.import_order_status_ids.mapped("status"):
            request.env["sale.order"].sudo().process_order_via_webhook(res, instance)
        return

    @http.route("/create_product_webhook_odoo", csrf=False, auth="public", type="json")
    def create_product_webhook(self):
        """
        Route for handling the product creation webhook of WooCommerce.
        This method will only process main products, not variations.
        @author: Maulik Barad on Date 21-Dec-2019.
        @modify:Haresh Mori on Date 31/12/2019
        """
        _logger.info("CREATE PRODUCT WEBHOOK call for this product: {0}".format(
            request.jsonrequest.get("name")))
        self.product_webhook_process()

    @http.route("/update_product_webhook_odoo", csrf=False, auth="public", type="json")
    def update_product_webhook(self):
        """
        Route for handling the product update webhook of WooCommerce.
        This method will only process main products, not variations.
        @author: Haresh Mori on Date 31-Dec-2019.
        """
        _logger.info(
            "UPDATE PRODUCT WEBHOOK call for this product: {0}".format(request.jsonrequest.get("name")))
        self.product_webhook_process()

    @http.route("/delete_product_webhook_odoo", csrf=False, auth="public", type="json")
    def delete_product_webhook(self):
        """
        Route for handling the product delete webhook for WooCommerce
        This method will only process main products, not variations.
        @author: Haresh Mori on Date 31-Dec-2019.
        """
        res, instance = self.get_basic_info()
        _logger.info("DELETE PRODUCT WEBHOOK call for this product: {0}".format(request.jsonrequest))
        woo_template = request.env["woo.product.template.ept"].sudo().search(
            [("woo_tmpl_id", "=", res.get('id')),
             ("woo_instance_id", "=", instance and instance.id)], limit=1)
        if woo_template:
            woo_template.write({'active': False})
        return

    @http.route("/restore_product_webhook_odoo", csrf=False, auth="public", type="json")
    def restore_product_webhook(self):
        """
        Route for handling the product restore webhook of WooCommerce.
        This method will only process main products, not variations.
        @author: Haresh Mori on Date 31-Dec-2019.
        """
        _logger.info(
            "RESTORE PRODUCT WEBHOOK call for this product: {0}".format(request.jsonrequest.get("name")))
        self.product_webhook_process()

    def product_webhook_process(self):
        """
        This method used to process the product webhook response.
        @author: Haresh Mori on Date 31-Dec-2019.
        """
        res, instance = self.get_basic_info()
        wcapi = instance.woo_connect()
        woo_template = request.env["woo.product.template.ept"].with_context(
            active_test=False).search([("woo_tmpl_id", "=", res.get('id')),
                                       ("woo_instance_id", "=", instance.id)], limit=1)
        if woo_template and instance.active:
            request.env["woo.product.data.queue.ept"].sudo().create_product_queue_from_webhook(res, instance, wcapi)

        elif res.get("status") == "publish" and res.get("type") != "variation" and instance.active:
            request.env["woo.product.data.queue.ept"].sudo().create_product_queue_from_webhook(res, instance, wcapi)

        return

    @http.route("/update_order_webhook_odoo", csrf=False, auth="public", type="json")
    def update_order_webhook(self):
        """
        Route for handling the order modification webhook of WooCommerce.
        @author: Maulik Barad on Date 21-Dec-2019.
        """
        res, instance = self.get_basic_info()

        if instance.active:
            if request.env["sale.order"].sudo().search_read([("woo_instance_id", "=", instance.id),
                                                             ("woo_order_id", "=", res.get("id")),
                                                             ("woo_order_number", "=", res.get("number"))],
                                                            ["id"]):
                request.env["sale.order"].sudo().process_order_via_webhook(res, instance, True)
            elif res.get("status") in instance.import_order_status_ids.mapped("status"):
                request.env["sale.order"].sudo().process_order_via_webhook(res, instance)

        return

    @http.route("/delete_order_webhook_odoo", csrf=False, auth="public", type="json")
    def delete_order_webhook(self):
        """
        Route for handling the order modification webhook of WooCommerce.
        @author: Maulik Barad on Date 21-Dec-2019.
        """
        res, instance = self.get_basic_info()
        res.update({"number": res.get("id"), "status": "cancelled"})

        if instance.active:
            order = request.env["sale.order"].sudo().search([("woo_instance_id", "=", instance.id),
                                                             ("woo_order_id", "=", res.get("id"))])
            if order:
                order_data_queue = order.create_woo_order_data_queue(instance, [res], "Order#" + str(res.get("id", "")),
                                                                     "webhook")
                order._cr.commit()
                order_data_queue.order_data_queue_line_ids.process_order_queue_line(update_order=True)
                _logger.info("Cancelled order {0} of {1} via Webhook as deleted in Woo Successfully".format(order.name,
                                                                                                            instance.name))
        return

    @http.route("/check_webhook", csrf=False, auth="public", type="json")
    def check_webhook(self):
        """
        Route for handling the order modification webhook of WooCommerce.
        @author: Maulik Barad on Date 21-Dec-2019.
        """
        res = request.jsonrequest
        headers = request.httprequest.headers
        event = headers.get("X-Wc-Webhook-Event")
        _logger.warning(
            "Record {0} {1} - {2} via Webhook".format(res.get("id"), event,
                                                      res.get("name", res.get("code", "")) if event != "deleted"
                                                      else "Done"))
        _logger.warning(res)
        return

    @http.route("/create_customer_webhook_odoo", csrf=False, auth="public", type="json")
    def create_customer_webhook(self):
        """
        Route for handling the customer creation webhook of WooCommerce.
        @author: Dipak Gogiya on Date 31-Dec-2019.
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "CREATE CUSTOMER WEBHOOK call for this Customer: {0}".format(request.jsonrequest))
        # Below method used for search the woo commerce customer base on woo customer id then after it searches in
        # res partner base on email without parent id
        woo_partner, odoo_partner = request.env['woo.res.partner.ept'].sudo().find_customer(
            instance, res)
        is_billing_address = any(res.get('billing').values())
        is_shipping_address = any(res.get('shipping').values())
        # Below method used to create a res partner record and shipping address when the billing
        # add did not exist in response.
        if not woo_partner and not odoo_partner and not is_billing_address:
            request.env['woo.res.partner.ept'].sudo().process_customers(instance, res,
                                                                        True if is_shipping_address else False,
                                                                        odoo_partner)
        # When the update customer webhook calls,below method used to create a res partner record
        # and shipping address.
        elif odoo_partner and odoo_partner.type == 'invoice' and not is_billing_address:
            request.env['woo.res.partner.ept'].check_partner_contact_address(res,
                                                                             odoo_partner,
                                                                             woo_partner, instance,
                                                                             is_shipping_address
                                                                             )
        else:
            # We create a new method for creating a customer queue. we have not to use the existing method because of
            # its parameter different.
            customer_queue = request.env['woo.customer.data.queue.ept'].sudo().create_customer_data_queue(instance, res,
                                                                                                          "webhook")
            # Below method used for when the woo customer id, billing address and shipping address exist in webhook
            # response.
            customer_queue.queue_line_ids.woo_customer_data_queue_to_odoo()
        return

    @http.route("/update_customer_webhook_odoo", csrf=False, auth="public", type="json")
    def update_customer_webhook(self):
        """
        Route for handling the customer update webhook of WooCommerce.
        @author: Dipak Gogiya on Date 01-Jan-2020
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "UPDATE CUSTOMER WEBHOOK call for this Customer: {0}".format(request.jsonrequest))
        woo_partner, odoo_partner = request.env['woo.res.partner.ept'].sudo().find_customer(
            instance, res)
        is_billing_address = any(res.get('billing').values())
        is_shipping_address = any(res.get('shipping').values())
        # Below method used to create a res partner record and shipping address when the billing
        # add did not exist in response.
        if not woo_partner and not odoo_partner and not is_billing_address:
            request.env['woo.res.partner.ept'].sudo().process_customers(instance, res,
                                                                        True if is_shipping_address else False,
                                                                        odoo_partner)
        # When the update customer webhook calls,below method used to create a res partner record
        # and shipping address.
        elif odoo_partner and odoo_partner.type == 'invoice' and not is_billing_address:
            request.env['woo.res.partner.ept'].check_partner_contact_address(res,
                                                                             odoo_partner,
                                                                             woo_partner, instance,
                                                                             is_shipping_address)

        else:
            # We create a new method for creating a customer queue. we have not to use the existing method because of
            # its parameter different.
            customer_queue = request.env['woo.customer.data.queue.ept'].sudo().create_customer_data_queue(instance, res,
                                                                                                          "webhook")
            # Below method used for when the woo customer id, billing address and shipping address exist in webhook
            # response.
            customer_queue.queue_line_ids.woo_customer_data_queue_to_odoo()
        return

    @http.route("/delete_customer_webhook_odoo", csrf=False, auth="public", type="json")
    def delete_customer_webhook(self):
        """
        Route for handling the customer deletion webhook of WooCommerce.
        @author: Dipak Gogiya on Date 31-Dec-2019
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "DELETE CUSTOMER WEBHOOK call for this Customer: {0}".format(request.jsonrequest))
        woo_partner = request.env['woo.res.partner.ept'].sudo().search(
            [('woo_customer_id', '=', res.get('id')), ('woo_instance_id', '=', instance.id)])
        if woo_partner:
            woo_partner.sudo().unlink()
        return

    @http.route("/create_coupon_webhook_odoo", csrf=False, auth="public", type="json")
    def create_coupon_webhook(self):
        """
        Route for handling the coupon create webhook of WooCommerce.
        @author: Haresh Mori on Date 1-Jan-2020.
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "CREATE COUPON WEBHOOK call for this coupon: {0}".format(res.get("code")))
        request.env["woo.coupon.data.queue.ept"].sudo().create_coupon_queue_from_webhook(res, instance)

    @http.route("/update_coupon_webhook_odoo", csrf=False, auth="public", type="json")
    def update_coupon_webhook(self):
        """
        Route for handling the coupon update webhook of WooCommerce.
        @author: Haresh Mori on Date 2-Jan-2020.
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "UPDATE COUPON WEBHOOK call for this coupon: {0}".format(res.get("code")))
        request.env["woo.coupon.data.queue.ept"].sudo().create_coupon_queue_from_webhook(res, instance)

    @http.route("/restore_coupon_webhook_odoo", csrf=False, auth="public", type="json")
    def restore_coupon_webhook(self):
        """
        Route for handling the coupon restore webhook of WooCommerce.
        @author: Haresh Mori on Date 2-Jan-2020.
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "RESTORE COUPON WEBHOOK call for this coupon: {0}".format(res.get("code")))
        request.env["woo.coupon.data.queue.ept"].sudo().create_coupon_queue_from_webhook(res, instance)

    @http.route("/delete_coupon_webhook_odoo", csrf=False, auth="public", type="json")
    def delete_coupon_webhook(self):
        """
        Route for handling the coupon delete webhook for WooCommerce
        @author: Haresh Mori on Date 2-Jan-2020.
        """
        res, instance = self.get_basic_info()
        _logger.info(
            "DELETE COUPON WEBHOOK call for this coupon: {0}".format(res))
        woo_coupon = request.env["woo.coupons.ept"].sudo().search(
            ["&", "|", ('coupon_id', '=', res.get("id")), ('code', '=', res.get("code")),
             ('woo_instance_id', '=', instance.id)],
            limit=1)
        if woo_coupon and instance.active:
            woo_coupon.write({'active': False})

        return

    def get_basic_info(self):
        """
        This method is used return basic info. It will return res and instance.
        @author: Haresh Mori on Date 2-Jan-2020.
        """
        res = request.jsonrequest
        headers = request.httprequest.headers
        host = headers.get("X-WC-Webhook-Source").rstrip('/')
        instance = request.env["woo.instance.ept"].sudo().search([("woo_host", "ilike", host)])
        return res, instance
