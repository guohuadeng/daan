"""
For woo_commerce_ept module.
"""
import ast
import logging
import pytz
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import Warning

_logger = logging.getLogger("Woo")


class SaleOrder(models.Model):
    """
    Inherited for importing and creating sale orders from WooCommerce.
    @author: Maulik Barad on Date 23-Oct-2019.
    """
    _inherit = "sale.order"

    def _get_woo_order_status(self):
        """
        Compute updated_in_woo of order from the pickings.
        @author: Maulik Barad on Date 04-06-2020.
        """
        for order in self:
            if order.woo_instance_id:
                pickings = order.picking_ids.filtered(lambda x:x.state != "cancel")
                if pickings:
                    outgoing_picking = pickings.filtered(
                        lambda x:x.location_dest_id.usage == "customer")
                    if all(outgoing_picking.mapped("updated_in_woo")):
                        order.updated_in_woo = True
                        continue
                elif order.woo_status == "completed":
                    """When all products are service type and no pickings are there."""
                    order.updated_in_woo = True
                    continue
                order.updated_in_woo = False
                continue
            order.updated_in_woo = True

    def _search_woo_order_ids(self, operator, value):
        query = """
                    select so.id from stock_picking sp
                    inner join sale_order so on so.procurement_group_id=sp.group_id                   
                    inner join stock_location on stock_location.id=sp.location_dest_id and stock_location.usage='customer'
                    where sp.updated_in_woo = %s and sp.state != 'cancel' and
                    so.woo_instance_id notnull
                """ % (value)
        self._cr.execute(query)
        results = self._cr.fetchall()
        order_ids = []
        for result_tuple in results:
            order_ids.append(result_tuple[0])
        order_ids = list(set(order_ids))
        return [('id', 'in', order_ids)]

    woo_order_id = fields.Char("Woo Order Reference", help="WooCommerce Order Reference", copy=False)
    woo_order_number = fields.Char("Order Number", help="WooCommerce Order Number", copy=False)
    auto_workflow_process_id = fields.Many2one("sale.workflow.process.ept", "Auto Workflow")
    woo_instance_id = fields.Many2one("woo.instance.ept", "Woo Instance", copy=False)
    payment_gateway_id = fields.Many2one("woo.payment.gateway", "Woo Payment Gateway", copy=False)
    woo_coupon_ids = fields.Many2many("woo.coupons.ept", string="Coupons", copy=False)
    woo_trans_id = fields.Char("Transaction ID", help="WooCommerce Order Transaction Id", copy=False)
    woo_customer_ip = fields.Char("Customer IP", help="WooCommerce Customer IP Address", copy=False)
    updated_in_woo = fields.Boolean("Updated In woo", compute="_get_woo_order_status",
                                    search="_search_woo_order_ids", copy=False)
    canceled_in_woo = fields.Boolean("Canceled In WooCommerce", default=False, copy=False)
    woo_status = fields.Selection([("pending", "Pending"), ("processing", "Processing"),
                                   ("on-hold", "On hold"), ("completed", "Completed"),
                                   ("cancelled", "Cancelled"), ("refunded", "Refunded")],
                                   copy=False, tracking=7)

    def create_woo_order_data_queue(self, woo_instance, orders_data, name="", created_by="import"):
        """
        Creates order data queues from the data got from API.
        @author: Maulik Barad on Date 04-Nov-2019.
        @param woo_instance: Instance of Woocommerce.
        @param orders_data: Imported JSON data of orders.
        """
        order_data_queue_obj = self.env["woo.order.data.queue.ept"]
        while orders_data:
            vals = {"name":name, "instance_id":woo_instance.id, "created_by":created_by}
            data = orders_data[:50]
            if data:
                order_data_queue = order_data_queue_obj.create(vals)
                _logger.info("New order queue %s created." % (order_data_queue.name))
                order_data_queue.create_woo_data_queue_lines(data)
                _logger.info("Lines added in Order queue %s." % (order_data_queue.name))
                del orders_data[:50]
        _logger.info("Import order process completed.")
        return order_data_queue

    @api.model
    def get_order_data_v3(self, params, woo_instance):
        """
        Fetch orders from WooCommerce for wc/v3 api version.
        @author: Maulik Barad on Date 21-11-2019.
        @param params: Dictionary of parameters to pass in request.
        @param woo_instance: Instance of Woo.
        @return: List of Dictionaries of orders.
        """
        orders_data = []
        statuses = woo_instance.import_order_status_ids.mapped("status")

        wcapi = woo_instance.woo_connect()
        from_date = params["after"][:10]
        to_date = params["before"][:10]
        for status in statuses:
            try:
                response = wcapi.get(
                        "orders?status=%s&filter[created_at_min]=%s&filter[created_at_max]=%s&filter[limit]=%d&page=%d&filter[order]=%s" % (
                            status, from_date, to_date, params["per_page"], params["page"],
                            params["order"]))
            except Exception as e:
                raise Warning(
                        "Something went wrong while importing orders.\n\nPlease Check your Connection and Instance Configuration.\n\n" + str(
                                e))
            if response.status_code != 200:
                log_line = self.create_woo_log_lines(
                        response.json().get("message", response.reason))
                self.env["common.log.book.ept"].create({"woo_instance_id":woo_instance.id,
                                                        "type":"import",
                                                        "module":"woocommerce_ept",
                                                        "active":True,
                                                        "log_lines":[(4, log_line.id, False)]
                                                        })
                return False

            orders_data += response.json().get("orders", [])

            total_pages = response.headers.get("X-WC-TotalPages")
            # If there are more than one pages.
            if int(total_pages) > 1:
                page_data = []
                for page in range(2, int(total_pages) + 1):
                    response = wcapi.get(
                            "orders?status=%s&filter[created_at_min]=%s&filter[created_at_max]=%s&filter[limit]=%d&page=%d&order=%s" % (
                                status, from_date, to_date, params["per_page"], page,
                                params["order"]))
                    page_data = response.json().get("orders", [])
                orders_data += page_data

        return orders_data

    @api.model
    def get_order_data_wc_v1_v2(self, params, woo_instance):
        """
        Fetch orders from WooCommerce for wc/v3 api version.
        @author: Maulik Barad on Date 21-11-2019.
        @param params: Dictionary of parameters to pass in request.
        @param woo_instance: Instance of Woo.
        @return: List of Dictionaries of orders.
        """
        orders_data = []
        statuses = woo_instance.import_order_status_ids.mapped("status")

        wcapi = woo_instance.woo_connect()
        for status in statuses:
            params["status"] = status
            try:
                response = wcapi.get("orders", params=params)
            except Exception as e:
                raise Warning(
                        "Something went wrong while importing orders.\n\nPlease Check your Connection and Instance Configuration.\n\n" + str(
                                e))

            if response.status_code != 200:
                log_line = self.create_woo_log_lines(
                        response.json().get("message", response.reason))
                self.env["common.log.book.ept"].create({"woo_instance_id":woo_instance.id,
                                                        "type":"import",
                                                        "module":"woocommerce_ept",
                                                        "active":True,
                                                        "log_lines":[(4, log_line.id, False)]
                                                        })
                return False

            orders_data += response.json()

            total_pages = response.headers.get("X-WP-TotalPages")
            # If there are more than one pages.
            if int(total_pages) > 1:
                page_data = []
                for page in range(2, int(total_pages) + 1):
                    params["page"] = page
                    response = wcapi.get("orders", params=params)
                    page_data = response.json()
                orders_data += page_data

        return orders_data

    @api.model
    def get_order_data_wc_v3(self, params, woo_instance):
        """
        Fetch orders from WooCommerce for wc/v3 api version.
        @author: Maulik Barad on Date 21-11-2019.
        @param params: Dictionary of parameters to pass in request.
        @param woo_instance: Instance of Woo.
        @return: List of Dictionaries of orders.
        """
        status = ",".join(map(str, woo_instance.import_order_status_ids.mapped("status")))
        params["status"] = status

        wcapi = woo_instance.woo_connect()
        try:
            response = wcapi.get("orders", params=params)
        except Exception as e:
            raise Warning(
                    "Something went wrong while importing orders.\n\nPlease Check your Connection and Instance Configuration.\n\n" + str(
                            e))

        if response.status_code != 200:
            log_line = self.create_woo_log_lines(str(response.status_code) + " || " + response.json().get("message", response.reason))
            self.env["common.log.book.ept"].create({"woo_instance_id":woo_instance.id,
                                                    "type":"import",
                                                    "module":"woocommerce_ept",
                                                    "active":True,
                                                    "log_lines":[(4, log_line.id, False)]
                                                    })
            return False

        orders_data = response.json()

        total_pages = response.headers.get("X-WP-TotalPages")
        # If there are more than one pages.
        if int(total_pages) > 1:
            for page in range(2, int(total_pages) + 1):
                params["page"] = page
                response = wcapi.get("orders", params=params)
                orders_data += response.json()

        return orders_data

    def import_woo_orders(self, woo_instance, from_date="", to_date=""):
        """
        Imports orders from woo commerce and creates order data queue.
        @author: Maulik Barad on Date 04-Nov-2019.
        @param woo_instance: Woo Instance to import orders from.
        @param from_date: Orders will be imported which are created after this date.
        @param to_date: Orders will be imported which are created before this date.
        """
        if isinstance(woo_instance, int):
            woo_instance = self.env["woo.instance.ept"].browse(woo_instance)
        if not woo_instance.active:
            return False

        from_date = from_date if from_date else woo_instance.last_order_import_date - timedelta(days=1) if woo_instance.last_order_import_date else fields.Datetime.now() - timedelta(days=1)
        to_date = to_date if to_date else fields.Datetime.now()

        from_date = pytz.utc.localize(from_date).astimezone(
                pytz.timezone(woo_instance.store_timezone)) if from_date else False
        to_date = pytz.utc.localize(to_date).astimezone(pytz.timezone(woo_instance.store_timezone))

        if woo_instance.woo_version == "v3":
            to_date += timedelta(days=1)

        params = {"after":str(from_date)[:19], "before":str(to_date)[:19],
                  "per_page":100, "page":1, "order":"asc"}

        orders_data = self.get_order_data_v3(params,
                                             woo_instance) if woo_instance.woo_version == "v3" else self.get_order_data_wc_v3(
                params,
                woo_instance) if woo_instance.woo_version == "wc/v3" else self.get_order_data_wc_v1_v2(
                params, woo_instance)
        woo_instance.last_order_import_date = to_date.astimezone(pytz.timezone("UTC")).replace(
                tzinfo=None)
        if not orders_data:
            _logger.info("No orders Found between %s and %s for %s" % (
                str(from_date), str(to_date), woo_instance.name))
            return True

        self.create_woo_order_data_queue(woo_instance, orders_data)
        return True

    @api.model
    def create_or_update_payment_gateway(self, instance, order):
        """
        Creates or updates payment gateway as per order's data.
        @author: Maulik Barad on Date 08-Nov-2019.
        @param instance: Woo instance.
        @param order: Data of order.
        @return: Record of payment gateway.
        """
        payment_gateway_obj = self.env["woo.payment.gateway"]

        if instance.woo_version == "v3":
            payment_data = order.get("payment_details", {})
            code = payment_data.get("method_id", "")
            name = payment_data.get("method_title", "")
        else:
            code = order.get("payment_method", "")
            name = order.get("payment_method_title", "")

        if not code:
            return False

        payment_gateway = payment_gateway_obj.search([("code", "=", code),
                                                      ("woo_instance_id", "=", instance.id)],
                                                     limit=1)
        if payment_gateway:
            payment_gateway.name = name
        else:
            payment_gateway = payment_gateway_obj.create({"code":code,
                                                          "name":name,
                                                          "woo_instance_id":instance.id})
        return payment_gateway

    def create_woo_log_lines(self, message, common_log_book_id=False, queue_line=False):
        """
        Creates log line for the failed queue line.
        @author: Maulik Barad on Date 09-Nov-2019.
        @param queue_line: Failed queue line.
        @param message: Cause of failure.
        @return: Created log line.
        """
        log_line_obj = self.env["common.log.lines.ept"]
        log_line_vals = {"message":message,
                         "model_id":log_line_obj.get_model_id(self._name)}
        if queue_line:
            log_line_vals.update({"woo_order_data_queue_line_id":queue_line.id})
            queue_line.state = "failed"
        if common_log_book_id:
            log_line_vals.update({"log_line_id":common_log_book_id.id})
        return log_line_obj.create(log_line_vals)

    def prepare_woo_order_vals(self, order_data, woo_instance, partner, shipping_partner, workflow,
                               payment_gateway):
        """
        Prepares order's values for creating it.
        @author: Maulik Barad on Date 08-Nov-2019.
        @param order_data: Data of woo order.
        @param woo_instance: Woo instance.
        @param partner: For partner and invoice partner.
        @param shipping_partner: For setting shipping partner.
        @param workflow: For adding picking policy and invoicing policy.
        @param payment_gateway: For payment gateway.
        @return: Dictionary of order's necessary field.
        """
        if woo_instance.woo_version == "v3":
            order_date = order_data.get("created_at").replace("Z", "")
        elif woo_instance.woo_version == "wc/v1":
            order_date = order_data.get("date_created")
        else:
            order_date = order_data.get("date_created_gmt")

        price_list = self.check_pricelist_for_order(order_data, woo_instance)

        ordervals = {
            "partner_id":partner.ids[0],
            "partner_shipping_id":shipping_partner.ids[0],
            "partner_invoice_id":partner.ids[0],
            "warehouse_id":woo_instance.woo_warehouse_id.id,
            "company_id":woo_instance.company_id.id,
            "pricelist_id":price_list.id,
            "payment_term_id":woo_instance.woo_payment_term_id.id,
            "date_order":order_date.replace("T", " "),
            "state":"draft",
        }
        woo_order_vals = self.create_sales_order_vals_ept(ordervals)

        woo_order_number = order_data.get("number")
        if woo_instance.order_prefix:
            name = "%s%s" % (woo_instance.order_prefix, woo_order_number)
        elif not woo_instance.custom_order_prefix:
            name = self.env["ir.sequence"].next_by_code("sale.order") or _("New")
        else:
            name = woo_order_number

        woo_order_vals.update({
            "name":name,
            "note":order_data.get("customer_note"),
            "woo_order_id":order_data.get("id"),
            "woo_order_number":woo_order_number,
            "woo_instance_id":woo_instance.id,
            "team_id":woo_instance.sales_team_id.id if woo_instance.sales_team_id else False,
            "payment_gateway_id":payment_gateway.id if payment_gateway else False,
            "woo_trans_id":order_data.get("transaction_id", ""),
            "woo_customer_ip":order_data.get("customer_ip_address"),
            "global_channel_id":woo_instance.global_channel_id.id if woo_instance.global_channel_id else False,
            "picking_policy":workflow.picking_policy,
            "auto_workflow_process_id":workflow.id,
            "partner_shipping_id":shipping_partner.ids[0],
            "woo_status":order_data.get("status"),
            "client_order_ref":woo_order_number
        })
        return woo_order_vals

    def check_pricelist_for_order(self, result, woo_instance):
        """
        This method use to check the order price list exists or not in odoo base on the order
        currency.
        @author: Haresh Mori on Date 06-Dec-2019.
        @:parameter : result
        """
        currency_obj = self.env["res.currency"]
        order_currency = result.get("currency")

        currency_id = currency_obj.search([('name', '=', order_currency)], limit=1)
        if not currency_id:
            currency_id = currency_obj.search([('name', '=', order_currency),
                                               ('active', '=', False)], limit=1)
            currency_id.write({'active':True})
        if woo_instance.woo_pricelist_id.currency_id.id == currency_id.id:
            return woo_instance.woo_pricelist_id
        price_list = self.env['product.pricelist'].search([('currency_id', '=', currency_id.id)],
                                                          limit=1)
        if price_list:
            return price_list

        price_list = self.env['product.pricelist'].create({'name':currency_id.name,
                                                           'currency_id':currency_id.id,
                                                           'company_id':woo_instance.company_id.id,
                                                           })

        return price_list

    @api.model
    def create_woo_tax(self, tax, tax_included, woo_instance):
        """
        Creates tax in odoo as woo tax.
        @author: Maulik Barad on Date 20-Nov-2019.
        @param tax: Dictionary of woo tax.
        @param tax_included: If tax is included or not in price of product in woo.
        @param company_id: Company set in Instance.
        """
        title = tax["name"]
        rate = tax["rate"]

        if tax_included:
            name = "%s (%s %% included)" % (title, rate)
        else:
            name = "%s (%s %% excluded)" % (title, rate)

        odoo_tax = self.env["account.tax"].create({"name":name, "amount":float(rate),
                                                   "type_tax_use":"sale",
                                                   "price_include":tax_included,
                                                   "company_id":woo_instance.company_id.id})

        odoo_tax.mapped("invoice_repartition_line_ids").write(
                {"account_id":woo_instance.invoice_tax_account_id.id})
        odoo_tax.mapped("refund_repartition_line_ids").write(
                {"account_id":woo_instance.credit_note_tax_account_id.id})

        return odoo_tax

    @api.model
    def apply_woo_taxes(self, taxes, tax_included, woo_instance):
        """
        Finds matching odoo taxes with woo taxes' rates.
        If no matching tax found in odoo, then creates a new one.
        @author: Maulik Barad on Date 20-Nov-2019.
        @param taxes: List of Dictionaries of woo taxes.
        @param tax_included: If tax is included or not in price of product in woo.
        @param woo_instance: Instance of Woo.
        @return: Taxes' ids in format to add in order line.
        """
        tax_obj = self.env["account.tax"]
        tax_ids = []
        for tax in taxes:
            rate = float(tax.get("rate"))
            tax_id = tax_obj.search([("price_include", "=", tax_included),
                                     ("type_tax_use", "=", "sale"),
                                     ("amount", "=", rate),
                                     ("company_id", "=",
                                      woo_instance.company_id.id)],
                                    limit=1)
            if not tax_id:
                tax_id = self.create_woo_tax(tax, tax_included, woo_instance)
            if tax_id:
                tax_ids.append(tax_id.id)

        return tax_ids

    @api.model
    def create_woo_order_line(self, line_id, product, quantity, order, price, taxes, tax_included,
                              woo_instance,
                              is_shipping=False):
        """
        Creates sale order line for the woo order.
        @author: Maulik Barad on Date 11-Nov-2019.
        @param line_id: Id of woo order line.
        @param product: Product to set in order line.
        @param quantity: Quantity of product.
        @param order: To create the order line of which sale order.
        @param price: Sale unit price of product in woo.
        @param taxes: List of Dictionaries of woo taxes.
        @param tax_included: If tax is included or not in price of product in woo.
        @param woo_instance: Instance of Woo.
        @param is_shipping: If the order line is shipping line.
        @return: Created sale order line. 
        """
        line_vals = {
            "name":product.name,
            "product_id":product.id,
            "product_uom":product.uom_id.id if product.uom_id else False,
            "order_id":order.id,
            "order_qty":quantity,
            "price_unit":price,
            "is_delivery":is_shipping,
            "company_id":woo_instance.company_id.id
        }

        woo_so_line_vals = self.env["sale.order.line"].create_sale_order_line_ept(line_vals)

        if woo_instance.apply_tax == "create_woo_tax":
            tax_ids = self.apply_woo_taxes(taxes, tax_included, woo_instance)
            woo_so_line_vals.update({"tax_id":[(6, 0, tax_ids)]})

        woo_so_line_vals.update({"woo_line_id":line_id})
        return self.env["sale.order.line"].create(woo_so_line_vals)

    @api.model
    def create_woo_sale_order_lines(self, queue_line, order_line_data, sale_order,
                                    tax_included, common_log_book_id,woo_taxes):
        """
        Checks for products and creates sale order lines.
        @author: Maulik Barad on Date 13-Nov-2019.
        @param queue_line: The queue line.
        @param order_line_data: JSON Data of order line.
        @param sale_order: Created sale order.
        @param woo_taxes: Dictionary of woo taxes.
        @param tax_included: If tax is included or not in price of product.
        @return: Created sale order lines.
        """
        order_lines_list = []
        for order_line in order_line_data:
            taxes = []
            woo_product = self.find_or_create_woo_product(queue_line, order_line,
                                                          common_log_book_id)
            if not woo_product:
                message = "Product is not found for sale order. Please check the configuration."
                self.create_woo_log_lines(message, common_log_book_id, queue_line)
                return False,woo_taxes
            product = woo_product.product_id
            actual_unit_price = 0.0
            if tax_included:
                actual_unit_price = (float(order_line.get("subtotal_tax")) + float(
                        order_line.get("subtotal"))) / float(
                        order_line.get("quantity"))
            else:
                actual_unit_price = float(order_line.get("subtotal")) / float(
                        order_line.get("quantity"))
            if queue_line.instance_id.apply_tax == "create_woo_tax":
                line_taxes = order_line.get("taxes")
                for tax in line_taxes:
                    if tax["id"] in woo_taxes.keys():
                        taxes.append(woo_taxes[tax["id"]])
                    else:
                        woo_taxes = self.get_tax_ids(sale_order.woo_instance_id,tax["id"],woo_taxes)
                        if tax["id"] in woo_taxes.keys():
                            taxes.append(woo_taxes[tax["id"]])
                        else:
                            message = """Tax is not found for sale order in WooCommerce Store.\n- Maybe the tax was removed from WooCommerce Store after the order was placed."""
                            self.create_woo_log_lines(message, common_log_book_id, queue_line)
                            return False,woo_taxes

            order_line_id = self.create_woo_order_line(order_line.get("id"), product,
                                                       order_line.get("quantity"), sale_order,
                                                       actual_unit_price, taxes, tax_included,
                                                       queue_line.instance_id)
            order_lines_list.append(order_line_id)
            # Add by Haresh Mori on date 04/12/2019, Below use for creating a separate line of discount.
            line_discount = float(order_line.get('subtotal')) - float(order_line.get('total')) or 0
            if line_discount > 0:
                if tax_included:
                    tax_discount = float(order_line.get("subtotal_tax", 0.0)) - float(
                            order_line.get("total_tax", 0.0)) or 0
                    line_discount = tax_discount + line_discount

                discount_line = self.create_woo_order_line(False,
                                                           queue_line.instance_id.discount_product_id,
                                                           1, sale_order, line_discount * -1, taxes,
                                                           tax_included, queue_line.instance_id)
                discount_line.write({'name':'Discount for ' + order_line_id.name})
                if queue_line.instance_id.apply_tax == 'odoo_tax':
                    discount_line.tax_id = order_line_id.tax_id

            _logger.info("Sale order line is created.")
        return order_lines_list,woo_taxes

    @api.model
    def find_or_create_woo_product(self, queue_line, order_line, common_log_book_id):
        """
        Searches for the product and return it.
        If it is not found and configuration is set to import product, it will collect data and
        create the product.
        @author: Maulik Barad on Date 12-Nov-2019.
        @param queue_line: Order data queue.
        @param order_line: Order line.
        @return: Woo product if found, otherwise blank object.
        """
        woo_product_template_obj = self.env["woo.product.template.ept"]
        woo_instance = queue_line.instance_id

        # Checks for the product. If found then returns it.
        woo_product_id = order_line.get("variation_id") if order_line.get(
                "variation_id") else order_line.get(
                "product_id")
        woo_product = woo_product_template_obj.search_odoo_product_variant(woo_instance,
                                                                           order_line.get("sku"),
                                                                           woo_product_id)[0]
        # If product not found and configuration is set to import product, then creates it.
        if not woo_product and woo_instance.auto_import_product:
            product_data = woo_product_template_obj.get_products_from_woo_v1_v2_v3(woo_instance,
                                                                                   common_log_book_id,
                                                                                   order_line.get(
                                                                                           "product_id"))
            woo_product_template_obj.sync_products(product_data, woo_instance,
                                                   common_log_book_id, order_queue_line=queue_line)
            woo_product = woo_product_template_obj.search_odoo_product_variant(woo_instance,
                                                                               order_line.get(
                                                                                       "sku"),
                                                                               woo_product_id)[0]
        return woo_product

    @api.model
    def get_tax_ids(self, woo_instance,tax_id,woo_taxes):
        """
        Fetches all taxes for the woo instance.
        @author: Maulik Barad on Date 20-Nov-2019.
        @param woo_instance: Woo Instance.
        @return: Tax data if no issue was there, otherwise the error message.
        """
        wcapi = woo_instance.woo_connect()
        params = {"_fields": "id,name,rate,shipping", "per_page": 100, "page": 1}
        try:
            response = wcapi.get("taxes/%s" % (tax_id), params=params)
            if response.status_code != 200:
                return response.json().get("message", response.reason)
            tax_data = response.json()
        except:
            return woo_taxes
        #         tax_data = response.json()["taxes"] if woo_instance.woo_version == "v3" else response.json()
        woo_taxes.update({tax_data["id"]: tax_data})
        return woo_taxes

    @api.model
    def verify_order_for_payment_method(self, order_data):
        """
        Check order for full discount, when there is no payment gateway found.
        @author: Maulik Barad on Date 21-May-2020.
        """
        total_discount = 0

        total = order_data.get("total")
        if order_data.get("coupon_lines"):
            total_discount = order_data.get("discount_total")

        if float(total) == 0 and float(total_discount) > 0:
            return True
        return False

    @api.model
    def create_woo_orders_wc_v1_v2_v3(self, queue_lines, common_log_book_id):
        """
        Create orders from the order queue lines.
        @Task: 157064 - Order Processing || Import || Update Order Status || Cancel
        @author: Maulik Barad on Date 06-Nov-2019.
        @param queue_lines: Order data queue lines.
        @return: Recordset of created sale orders.
        """
        delivery_carrier_obj = self.env["delivery.carrier"]
        product_template_obj = self.env["product.template"]
        woo_coupon_obj = self.env["woo.coupons.ept"]
        sale_auto_workflow_obj = self.env["woo.sale.auto.workflow.configuration"]
        new_orders = self
        woo_instance = False
        commit_count = 0
        woo_taxes={}
        for queue_line in queue_lines:
            commit_count += 1
            if commit_count == 5:
                # This is used for commit every 5 orders
                queue_line.order_data_queue_id.is_process_queue = True
                self._cr.commit()
                commit_count = 0
            if woo_instance != queue_line.instance_id:
                woo_instance = queue_line.instance_id
#                woo_taxes = {}
#                if woo_instance.apply_tax == "create_woo_tax":
#                    woo_taxes = self.get_tax_ids(woo_instance)
#                    if isinstance(woo_taxes, str):
#                        self.create_woo_log_lines(woo_taxes, common_log_book_id, queue_line)
#                        continue

            if not queue_line.order_data:
                queue_line.state = "failed"
                continue

            order_data = ast.literal_eval(queue_line.order_data)
            queue_line.processed_at = fields.Datetime.now()
            existing_order = self.search([("woo_instance_id", "=", woo_instance.id),
                                          ("woo_order_id", "=", order_data.get("id")),
                                          ("woo_order_number", "=", order_data.get("number"))]).ids
            if not existing_order:
                existing_order = self.search([("woo_instance_id", '=', woo_instance.id),
                                              ("client_order_ref", "=", order_data.get("number"))]).ids
            if existing_order:
                queue_line.state = "done"
                continue

            financial_status = "paid"
            if order_data.get("transaction_id"):
                financial_status = "paid"
            elif order_data.get("date_paid") and order_data.get("payment_method") != "cod" and order_data.get("status") == "processing":
                financial_status = "paid"
            else:
                financial_status = "not_paid"

            workflow_config = False
            no_payment_gateway = False

            payment_gateway = self.create_or_update_payment_gateway(woo_instance, order_data)
            no_payment_gateway = self.verify_order_for_payment_method(order_data)

            if payment_gateway:
                workflow_config = sale_auto_workflow_obj.search(
                        [("woo_instance_id", "=", woo_instance.id),
                         ("woo_financial_status", "=", financial_status),
                         ("woo_payment_gateway_id", "=", payment_gateway.id)], limit=1)
            elif no_payment_gateway:
                payment_gateway = self.env['woo.payment.gateway'].search([
                    ("code", "=", "no_payment_method"), ("woo_instance_id", "=", woo_instance.id)])
                workflow_config = sale_auto_workflow_obj.search(
                    [("woo_instance_id", "=", woo_instance.id),
                     ("woo_financial_status", "=", financial_status),
                     ("woo_payment_gateway_id", "=", payment_gateway.id)], limit=1)
            else:
                message = """- System could not find the payment gateway response from WooCommerce store.\n- The response received from Woocommerce store was - Empty."""
                self.create_woo_log_lines(message, common_log_book_id, queue_line)
                queue_line.write({"state":"failed"})
                continue

            if not workflow_config:
                message = """- While creating order, based on combination of Payment Gateway '%s' and Woo Financial Status is %s,\n system tries to find out what all automated operations are to be applied on that given sales order.\n- Unfortunately system couldn't find that record under Financial Status records.\n- Please configure it under Woo configuration -> Financial Status and try again.""" % (
                    financial_status, order_data.get("payment_method"))

                # message = "Workflow not found for Payment Gateway %s and financial status is %s." % (
                #     financial_status, order_data.get("payment_method"))
                self.create_woo_log_lines(message, common_log_book_id, queue_line)
                continue

            workflow = workflow_config.woo_auto_workflow_id
            if not workflow.picking_policy:
                message = """- It seems Picking Policy value required to manage the Delivery Order is not set under Auto Workflow named %s.\n- Please configure it under WooCommerce -> Configuration -> Sales Auto Workflow.""" % (
                    workflow.name)
                # message = "Sale Auto Workflow is not configured properly. Please check it."
                self.create_woo_log_lines(message, common_log_book_id, queue_line)
                continue

            woo_customer_id = order_data.get("customer_id", False)
            partner_obj = self.env['res.partner']
            partner = partner_obj.woo_create_or_update_customer(woo_customer_id,
                                                         order_data.get("billing"), True,
                                                         instance=woo_instance)
            parent_id = partner.id
            if partner.parent_id:
                parent_id = partner.parent_id.id
            shipping_partner = partner_obj.woo_create_or_update_customer(False, order_data.get("shipping"), False,
                                                                  parent_id=parent_id,
                                                                  type="delivery",
                                                                  instance=woo_instance) if order_data.get("shipping", False) else partner

            if not shipping_partner:
                shipping_partner = partner

            order_vals = self.prepare_woo_order_vals(order_data, woo_instance, partner,
                                                     shipping_partner, workflow, payment_gateway)

            sale_order = self.create(order_vals)

            tax_included = order_data.get("prices_include_tax")

            order_lines,woo_taxes = self.create_woo_sale_order_lines(queue_line, order_data.get(
                    "line_items"), sale_order, tax_included, common_log_book_id,woo_taxes)
            if not order_lines:
                sale_order.sudo().unlink()
                queue_line.state = "failed"
                continue

            for shipping_line in order_data.get("shipping_lines"):
                delivery_method = shipping_line.get("method_title")
                if delivery_method:
                    carrier = delivery_carrier_obj.search(
                            [("woo_code", "=", delivery_method)], limit=1)
                    if not carrier:
                        carrier = delivery_carrier_obj.search(
                                [("name", "=", delivery_method)], limit=1)
                    if not carrier:
                        carrier = delivery_carrier_obj.search(
                                ["|", ("name", "ilike", delivery_method),
                                 ("woo_code", "ilike", delivery_method)], limit=1)
                    if not carrier:
                        product_template = product_template_obj.search(
                                [("name", "=", delivery_method),
                                 ("type", "=", "service")], limit=1)
                        if not product_template:
                            product_template = product_template_obj.create(
                                    {"name":delivery_method,
                                     "type":"service"})

                        carrier = delivery_carrier_obj.create({"name":delivery_method,
                                                               "woo_code":delivery_method,
                                                               "fixed_price":shipping_line.get("total"),
                                                               "product_id":product_template.product_variant_ids[0].id})
                    shipping_product = carrier.product_id
                    sale_order.write({"carrier_id":carrier.id})

                    taxes = []
                    if woo_taxes:
                        line_taxes = shipping_line.get("taxes")
                        for tax in line_taxes:
                            taxes.append(woo_taxes[tax["id"]])

                    if tax_included:
                        total_shipping = float(shipping_line.get("total", 0.0)) + float(shipping_line.get("total_tax", 0.0))
                    else:
                        total_shipping = float(shipping_line.get("total", 0.0))
                    self.create_woo_order_line(shipping_line.get("id"), shipping_product, 1,
                                               sale_order, total_shipping, taxes,
                                               tax_included, woo_instance, True)
                    _logger.info("Shipping line is created.")

            for fee_line in order_data.get("fee_lines"):
                if tax_included:
                    total_fee = float(fee_line.get("total", 0.0)) + float(fee_line.get("total_tax", 0.0))
                else:
                    total_fee = float(fee_line.get("total", 0.0))
                if total_fee:
                    taxes = []
                    if woo_taxes:
                        line_taxes = fee_line.get("taxes")
                        for tax in line_taxes:
                            taxes.append(woo_taxes[tax["id"]])

                    self.create_woo_order_line(fee_line.get("id"), woo_instance.fee_line_id, 1,
                                               sale_order, total_fee, taxes, tax_included,
                                               woo_instance)
                    _logger.info("Fee line is created.")

            woo_coupons = []
            for coupon_line in order_data.get("coupon_lines"):
                coupon_code = coupon_line["code"]
                coupon = woo_coupon_obj.search([("code", "=", coupon_code),
                                                ("woo_instance_id", "=", woo_instance.id)])
                if coupon:
                    woo_coupons.append(coupon.id)
                    _logger.info("Coupon {0} added.".format(coupon_code))
                else:
                    message = "The coupon {0} could not be added as it is not imported in odoo.".format(coupon_line["code"])
                    sale_order.message_post(body=message)
                    _logger.info("Coupon {0} not found.".format(coupon_line["code"]))
            sale_order.woo_coupon_ids = [(6, 0, woo_coupons)]

            customer_loc = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
            if order_data.get('status') == 'completed':
                sale_order.auto_workflow_process_id.shipped_order_workflow(sale_order,customer_loc)
            else:
                self.env["sale.workflow.process.ept"].auto_workflow_process(
                        sale_order.auto_workflow_process_id.id,
                        sale_order.ids)
            new_orders += sale_order
            queue_line.write({"sale_order_id":sale_order.id, "state":"done"})
            _logger.info("Sale order %s is created from queue line." % (order_data.get("id")))
        # Below line add by Haresh Mori on date 7/1/2020 this is used for set the is queue process
        # as False,To manage which queue is running in background.
        queue_lines.order_data_queue_id.is_process_queue = False
        return new_orders

    @api.model
    def update_woo_order_status(self, woo_instance):
        """
        Updates order's status in WooCommerce.
        @author: Maulik Barad on Date 14-Nov-2019.
        @param woo_instance: Woo Instance.
        """
        if isinstance(woo_instance, int):
            woo_instance = self.env["woo.instance.ept"].browse(woo_instance)
        wcapi = woo_instance.woo_connect()
        sales_orders = self.search([("warehouse_id", "=", woo_instance.woo_warehouse_id.id),
                                    ("woo_order_id", "!=", False),
                                    ("woo_instance_id", "=", woo_instance.id)])
        log_lines = self.env["common.log.lines.ept"]
        count = 0
        for sale_order in sales_orders:
            if sale_order.updated_in_woo == True:
                continue

            count += 1
            if count > 50:
                self._cr.commit()
                count = 1

            data = {"status":"completed"}
            order_completed = False
            pickings = sale_order.picking_ids

            for picking in pickings:
                """Only done picking and not updated in woo."""
                if picking.updated_in_woo or picking.state != "done" or picking.location_dest_id.usage != "customer":
                    continue

                if woo_instance.woo_version == "v3":
                    data = {"order":data}
                response = wcapi.put("orders/%s" % (sale_order.woo_order_id), data)

                if response.status_code not in [200, 201]:
                    _logger.info("Could not update status of Order %s." % (sale_order.woo_order_id))
                    message = "Error in updating status of order %s,  %s" % (
                        sale_order.name, response.content)
                    log_lines += self.create_woo_log_lines(message)
                    continue
                picking.write({"updated_in_woo":True})
                order_completed = True

            """When all products are service type."""
            if not pickings and sale_order.state == "sale":
                response = wcapi.put("orders/%s" % (sale_order.woo_order_id), data)

                if response.status_code not in [200, 201]:
                    _logger.info("Could not update status of Order %s." % (sale_order.woo_order_id))
                    message = "Error in updating status of order %s,  %s" % (
                        sale_order.name, response.content)
                    log_lines += self.create_woo_log_lines(message)
                    continue
                order_completed = True

            if order_completed:
                sale_order.woo_status = "completed"
            _logger.info("Done Order update status for Order : %s" % (sale_order.name))

        if log_lines:
            self.env["common.log.book.ept"].create({"type":"export",
                                                    "module":"woocommerce_ept",
                                                    "woo_instance_id":woo_instance.id,
                                                    "log_lines":[(6, 0, log_lines.ids)],
                                                    "active":True})
        return True

    def cancel_in_woo(self):
        """
        This method used to open a wizard to cancel order in WooCommerce.
        @param : self
        @return: action
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 23-11-2019.
        :Task id: 156886
        """
        view = self.env.ref('woo_commerce_ept.view_woo_cancel_order_wizard')
        context = dict(self._context)
        context.update({'active_model':'sale.order', 'active_id':self.id, 'active_ids':self.ids})
        return {
            'name':_('Cancel Order In WooCommerce'),
            'type':'ir.actions.act_window',
            'view_type':'form',
            'view_mode':'form',
            'res_model':'woo.cancel.order.wizard',
            'views':[(view.id, 'form')],
            'view_id':view.id,
            'target':'new',
            'context':context
        }

    @api.model
    def process_order_via_webhook(self, order_data, instance, update_order=False):
        """
        Creates order data queue and process it.
        This method is for order imported via create and update webhook.
        @author: Maulik Barad on Date 30-Dec-2019.
        @param order_data: Dictionary of order's data.
        @param instance: Instance of Woo.
        """
        order_data_queue = self.create_woo_order_data_queue(instance, [order_data],
                                                            "Order#" + order_data.get("number", ""),
                                                            "webhook")
        self._cr.commit()

        if order_data_queue:
            if update_order and self.search_read([("woo_instance_id", "=", instance.id),
                                                  ("woo_order_id", "=", order_data.get("id")),
                                                  ("woo_order_number", "=", order_data.get("number"))], ["id"]):
                order_data_queue.order_data_queue_line_ids.process_order_queue_line(update_order)
                _logger.info("Updated order {0} of {1} via Webhook Successfully".format(order_data.get("id"), instance.name))
            else:
                order_data_queue.order_data_queue_line_ids.process_order_queue_line()
                _logger.info("Imported order {0} of {1} via Webhook Successfully".format(order_data.get("id"), instance.name))
        _logger.info("Processed order {0} of {1} via Webhook Successfully".format(order_data.get("id"), instance.name))
        return True

    @api.model
    def update_woo_order(self, queue_line, log_book):
        """
        This method will update order as per its status got from WooCommerce.
        @author: Maulik Barad on Date 31-Dec-2019.
        @param queue_line: Order Data Queue Line.
        @param log_book: Common Log Book.
        @return: Updated Sale order.
        """
        message = ""
        woo_instance = queue_line.instance_id
        order_data = ast.literal_eval(queue_line.order_data)
        queue_line.processed_at = fields.Datetime.now()
        woo_status = order_data.get("status")
        order = self.search([("woo_instance_id", "=", woo_instance.id),
                             ("woo_order_id", "=", order_data.get("id"))])

        if woo_status == "cancelled" and order.state != "cancel":
            cancelled = order.cancel_woo_order()
            if not cancelled:
                message = "System can not cancel the order {0} as one of the picking is in the done state.".format(order.name)
        elif woo_status == "refunded":
            refunded = order.create_woo_refund(order_data.get("refunds"), woo_instance)
            if refunded[0] == 0:
                message = "System can not generate a refund as the invoice is not found. Please first create an invoice."
            elif refunded[0] == 1:
                message = "System can not generate a refund as the invoice is not posted. Please first post the invoice."
            elif refunded[0] == 2:
                message = "Currently partial refund is created in Woo. Either create credit note manual or refund fully."
        elif woo_status == "completed":
            completed = order.complete_woo_order()
            if isinstance(completed, bool) and not completed:
                message = "System can not complete the picking as there is not enough quantity."
            elif not completed:
                message = "System can not complete the picking as {0}".format(completed)

        if message:
            order.create_woo_log_lines(message, log_book, queue_line)
        else:
            queue_line.state = "done"
            order.woo_status = woo_status
        return order

    def cancel_woo_order(self):
        """
        Cancelled the sale order when it is cancelled in WooCommerce.
        @author: Maulik Barad on Date 31-Dec-2019.
        """
        if "done" in self.picking_ids.mapped("state"):
            return False
        self.action_cancel()
        return True

    def complete_woo_order(self):
        """
        If order is confirmed yet, confirms it first.
        Make the picking done, when order will be completed in WooCommerce.
        This method is used for Update order webhook.
        @author: Maulik Barad on Date 31-Dec-2019.
        """
        if not self.state == "sale":
            self.action_confirm()
        return self.complete_picking_for_woo(self.picking_ids.filtered(lambda x: x.location_dest_id.usage == "customer"))

    def complete_picking_for_woo(self, pickings):
        """
        It will make the pickings done.
        This method is used for Update order webhook.
        @author: Maulik Barad on Date 01-Jan-2020.
        """
        for picking in pickings.filtered(lambda x: x.state == "done"):
            picking.updated_in_woo = True
        for picking in pickings.filtered(lambda x: x.state != "done"):
            if picking.state != "assigned":
                if picking.move_lines.move_orig_ids:
                    completed = self.complete_picking_for_woo(picking.move_lines.move_orig_ids.picking_id)
                    if not completed:
                        return False
                picking.action_assign()
                if picking.state != "assigned":
                    return False
            result = picking.button_validate()
            if isinstance(result, dict):
                if result.get("res_model", "") == "stock.immediate.transfer":
                    immediate_transfer = self.env["stock.immediate.transfer"].browse(result.get("res_id"))
                    immediate_transfer.process()
                elif result.get("res_model", "") == "stock.backorder.confirmation":
                    backorder = self.env["stock.backorder.confirmation"].browse(result.get("res_id"))
                    backorder._process()
            else:
                return result
        return True

    def create_woo_refund(self, refunds_data, woo_instance):
        """
        Creates refund of Woo order, when order is refunded in WooCommerce.
        It will need invoice created and posted for creating credit note in Odoo, otherwise it will
        create log and generate activity as per configuration.
        @author: Maulik Barad on Date 02-Jan-2019.
        @param refunds_data: Data of refunds.
        @param woo_instance: Instance of Woo.
        @return:[0] : When no invoice is created.
                [1] : When invoice is not posted.
                [2] : When partial refund was made in Woo.
                [True]:When credit notes are created or partial refund is done.
        """
        if not self.invoice_ids:
            return [0]
        total_refund = 0.0
        for refund in refunds_data:
            total_refund += float(refund.get("total", 0)) * -1
        invoices = self.invoice_ids.filtered(lambda x: x.type == "out_invoice")
        refunds = self.invoice_ids.filtered(lambda x: x.type == "out_refund")
        for invoice in invoices:
            if not invoice.state == "posted":
                return [1]
        if self.amount_total == total_refund:
            move_reversal = self.env["account.move.reversal"].create({"refund_method":"cancel",
                                                                      "reason":"Refunded from Woo" if len(refunds_data) > 1 else refunds_data[0].get("reason")})
            move_reversal.with_context({"active_model":"account.move",
                                        "active_ids":invoices.ids}).reverse_moves()
            return [True]
        return [2]

    def _prepare_invoice(self):
        """
        This method is used to set instance id to invoice. for identified invoice.
        :return: invoice
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 23-11-2019.
        :Task id: 156886
        """
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.woo_instance_id:
            invoice_vals.update({'woo_instance_id':self.woo_instance_id.id})
        return invoice_vals


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    woo_line_id = fields.Char()
