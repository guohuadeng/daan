"""
For woo_commerce_ept module.
"""
import requests
import logging
from .. import woocommerce
from odoo import models, fields, api, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import Warning

_logger = logging.getLogger("Woo")


class woo_instance_ept(models.Model):
    _name = "woo.instance.ept"
    _description = "WooCommerce Instance"
    _check_company_auto = True


    @api.model
    def copy_product_template_data(self):
        _logger.info("Copy data method is executing")

        try : # Woo product Template
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_product_template_ept' AND column_name='woo_tmpl_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_product_template_ept set woo_tmpl_id=woo_tmpl_id_moved0 where woo_tmpl_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_product_template_ept set woo_tmpl_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # Woo product
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_product_product_ept' AND column_name='variant_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_product_product_ept set variant_id=variant_id_moved0 where variant_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_product_product_ept set variant_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # Woo product Image
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_product_image_ept' AND column_name='woo_image_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_product_image_ept set woo_image_id=woo_image_id_moved0 where woo_image_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_product_image_ept set woo_image_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # Woo product coupons
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_coupons_ept' AND column_name='coupon_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_coupons_ept set coupon_id=coupon_id_moved0 where coupon_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_coupons_ept set coupon_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # WOo product Category
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_product_categ_ept' AND column_name='woo_categ_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_product_categ_ept set woo_categ_id=woo_categ_id_moved0 where woo_categ_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_product_categ_ept set woo_categ_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # Woo Product Tags
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_tags_ept' AND column_name='woo_tag_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_tags_ept set woo_tag_id=woo_tag_id_moved0 where woo_tag_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_tags_ept set woo_tag_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass
        try : # Woo Webhook
            self._cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='woo_webhook_ept' AND column_name='woo_id_moved0')")
            result = self._cr.fetchall()
            for id in result :
                result = id[0]
            if result :
                qry = "update woo_webhook_ept set woo_id=woo_id_moved0 where woo_id_moved0 is not null"
                self._cr.execute(qry)
                qry = "update woo_webhook_ept set woo_id_moved0=NULL"
                self._cr.execute(qry)
            else :
                _logger.info("No need to update")
        except Exception as e :
            _logger.info(qry)
            _logger.info("Exception occured while execute query %s"%e)
            pass


    @api.model
    def _get_default_warehouse(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)],
                                                       limit=1, order='id')
        return warehouse.id if warehouse else False

    @api.model
    def _default_stock_field(self):
        stock_field = self.env['ir.model.fields'].search(
            [('model_id.model', '=', 'product.product'), ('name', '=', 'virtual_available')],
            limit=1)
        return stock_field.id if stock_field else False

    @api.model
    def _get_default_language(self):
        lang_code = self.env.user.lang
        language = self.env["res.lang"].search([('code', '=', lang_code)])
        return language.id if language else False

    @api.model
    def _default_payment_term(self):
        payment_term = self.env.ref("account.account_payment_term_immediate")
        return payment_term.id if payment_term else False

    @api.model
    def _default_order_status(self):
        """
        Return default status of woo order, for importing the particular orders having this status.
        @author: Maulik Barad on Date 11-Nov-2019.
        """
        order_status = self.env.ref('woo_commerce_ept.processing')
        return [(6, 0, [order_status.id])] if order_status else False

    @api.model
    def _default_discount_product(self):
        """
        Gives default discount product to set in imported woo order.
        @author: Maulik Barad on Date 11-Nov-2019.
        """
        discount_product = self.env.ref('woo_commerce_ept.product_woo_discount_ept') or False
        return discount_product

    @api.model
    def _default_fee_product(self):
        """
        Gives default discount product to set in imported woo order.
        @author: Maulik Barad on Date 11-Nov-2019.
        """
        fee_product = self.env.ref('woo_commerce_ept.product_woo_shipping_fees_ept') or False
        return fee_product

    @api.model
    def _woo_tz_get(self):
        """
        Gives all timezones from base.
        @author: Maulik Barad on Date 18-Nov-2019.
        @return: Calls base method for all timezones.
        """
        return _tz_get(self)

    def _compute_all(self):
        """
        Counts all attributes of Woo instance.
        @author: Dipak Gogiya.
        """
        for instance in self:
            instance.product_count = len(instance.product_ids)
            instance.sale_order_count = len(instance.sale_order_ids)
            instance.picking_count = len(instance.picking_ids)
            instance.invoice_count = len(instance.invoice_ids)
            instance.exported_product_count = len(instance.product_ids.filtered(lambda x: x.exported_in_woo))
            instance.ready_to_export_product_count = len(instance.product_ids.filtered(lambda x: not x.exported_in_woo))
            instance.published_product_count = len(instance.product_ids.filtered(lambda x: x.website_published))
            instance.unpublished_product_count = len(
                instance.product_ids.filtered(lambda x: not x.website_published and x.exported_in_woo))
            instance.quotation_count = len(instance.sale_order_ids.filtered(lambda x: x.state in ['draft', 'sent']))
            instance.order_count = len(
                instance.sale_order_ids.filtered(lambda x: x.state not in ['draft', 'sent', 'cancel']))
            instance.confirmed_picking_count = len(instance.picking_ids.filtered(lambda x: x.state == 'confirmed'))
            instance.partially_available_picking_count = len(
                instance.picking_ids.filtered(lambda x: x.state == 'partially_available'))
            instance.assigned_picking_count = len(instance.picking_ids.filtered(lambda x: x.state == 'assigned'))
            instance.done_picking_count = len(instance.picking_ids.filtered(lambda x: x.state == 'done'))
            instance.open_invoice_count = len(instance.invoice_ids.filtered(
                lambda x: x.state == 'posted' and x.type == 'out_invoice' and not x.invoice_payment_state == 'paid'))
            instance.paid_invoice_count = len(instance.invoice_ids.filtered(
                lambda x: x.state == 'posted' and x.invoice_payment_state == 'paid' and x.type == 'out_invoice'))
            instance.refund_invoice_count = len(instance.invoice_ids.filtered(lambda x: x.type == 'out_refund'))

    name = fields.Char(size=120, required=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)
    woo_country_id = fields.Many2one("res.country", "Country")
    woo_host = fields.Char("Host", required=True)
    auto_import_product = fields.Boolean(string="Auto Create Product if not found?", default=False)
    sync_price_with_product = fields.Boolean("Sync Product Price?",
                                             help="Check if you want to import price along with "
                                                  "products", default=True)
    sync_images_with_product = fields.Boolean("Sync Images?",
                                              help="Check if you want to import images along with "
                                                   "products", default=True)
    woo_consumer_key = fields.Char("Consumer Key", required=True,
                                   help="Login into WooCommerce site,Go to Admin Panel >> "
                                        "WooCommerce >> Settings >> API >> Keys/Apps >> "
                                        "Click on Add Key")
    woo_consumer_secret = fields.Char("Consumer Secret", required=True,
                                      help="Login into WooCommerce site,Go to Admin "
                                           "Panel >> WooCommerce >> Settings >> API "
                                           ">> "
                                           "Keys/Apps >> Click on Add Key")
    woo_verify_ssl = fields.Boolean("Verify SSL", default=False,
                                    help="Check this if your WooCommerce site is using SSL "
                                         "certificate")
    woo_is_image_url = fields.Boolean("Is Image URL?",
                                      help="Check this if you use Images from URL\nKeep as it is if "
                                           "you use Product images")
    woo_admin_username = fields.Char("Username",
                                     help="WooCommerce UserName,Used to Export Image Files.")
    woo_admin_password = fields.Char("Password",
                                     help="WooCommerce Password,Used to Export Image Files.")
    woo_version = fields.Selection(
        [("v3", "Below 2.6"), ("wc/v1", "2.6 To 2.9"), ("wc/v2", "3.0 To 3.4"), ("wc/v3", "3.5+")],
        string="WooCommerce Version", default="wc/v3",
        help="Set the appropriate WooCommerce Version you are using currently or\nLogin "
             "into WooCommerce site,Go to Admin Panel >> Plugins")
    state = fields.Selection([('not_confirmed', 'Not Confirmed'), ('confirmed', 'Confirmed')],
                             default='not_confirmed')
    woo_pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    woo_stock_field = fields.Many2one('ir.model.fields', string='Stock Field',
                                      default=_default_stock_field)
    woo_last_synced_order_date = fields.Datetime(string="Last Date of Import Order",
                                                 help="Which from date to import woo order from woo commerce")
    woo_warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', check_company=True,
                                       default=_get_default_warehouse, required=True)
    woo_visible = fields.Boolean("Visible on the product page?", default=True,
                                 help="""Attribute is visible on the product page""")
    woo_attribute_type = fields.Selection([("select", "Select"), ("text", "Text")],
                                          string="Attribute Type",
                                          default="select")
    woo_auto_active_currency = fields.Boolean("Auto Active Currency", default=True,
                                              help="Automatically changes currency state to active if it is inactive.")
    woo_currency_id = fields.Many2one("res.currency", string="Currency",
                                      help="Woo Commerce Currency.")
    woo_lang_id = fields.Many2one('res.lang', string='Language', default=_get_default_language)
    woo_payment_term_id = fields.Many2one('account.payment.term', string='Payment Term',
                                          default=_default_payment_term)
    color = fields.Integer("Color Index")
    import_order_status_ids = fields.Many2many("import.order.status.ept",
                                               "woo_instance_order_status_rel",
                                               "instance_id",
                                               "status_id", "Import Order Status",
                                               default=_default_order_status,
                                               help="Selected status orders will be imported from WooCommerce")
    last_order_import_date = fields.Datetime(string="Last Order Import Date",
                                             help="This date is used to import order from this date.")
    sales_team_id = fields.Many2one('crm.team',
                                    help="Choose Sales Team that handles the order you import.")
    global_channel_id = fields.Many2one('global.channel.ept')
    custom_order_prefix = fields.Boolean("Use Custom Order Prefix",
                                         help="""True:Use Custom Order Prefix,
                                             False:Default Sale Order Prefix""")
    order_prefix = fields.Char(size=10, help="Custom order prefix for Woocommerce orders.")
    discount_product_id = fields.Many2one("product.product", "Discount",
                                          domain=[('type', '=', 'service')],
                                          default=_default_discount_product)
    fee_line_id = fields.Many2one("product.product", "Fees", domain=[('type', '=', 'service')],
                                  default=_default_fee_product)
    last_inventory_update_time = fields.Datetime("Last Inventory Update Time")
    woo_stock_auto_export = fields.Boolean(string="Woo Stock Auto Update",
                                           help="Check if you want to automatically update stock levels from Odoo to "
                                                "WooCommerce.")
    auto_import_order = fields.Boolean("Auto Import Order from Woo?",
                                       help="Imports orders at certain interval.")
    auto_update_order_status = fields.Boolean(string="Auto Update Order Status in Woo?",
                                              help="Automatically update order status to WooCommerce.")
    store_timezone = fields.Selection("_woo_tz_get", help="Timezone of Store for requesting data.")
    apply_tax = fields.Selection(
        [("odoo_tax", "Odoo Default Tax"), ("create_woo_tax", "Create new tax if not found")],
        default="create_woo_tax", copy=False,
        help=""" For Woocommerce Orders :- \n
                    1) Odoo Default Tax Behavior - The Taxes will be set based on Odoo's
                                 default functional behavior i.e. based on Odoo's Tax and Fiscal Position 
                                 configurations. \n
                    2) Create New Tax If Not Found - System will search the tax data received 
                    from Woocommerce in Odoo, will create a new one if it fails in finding it.""")
    invoice_tax_account_id = fields.Many2one('account.account', string='Invoice Tax Account')
    credit_note_tax_account_id = fields.Many2one('account.account',
                                                 string='Credit Note Tax Account')
    product_ids = fields.One2many('woo.product.template.ept', 'woo_instance_id', string="Products")
    product_count = fields.Integer(compute='_compute_all', string="Products Count")
    sale_order_ids = fields.One2many('sale.order', 'woo_instance_id', string="Orders")
    sale_order_count = fields.Integer(compute='_compute_all', string="Orders Count")
    picking_ids = fields.One2many('stock.picking', 'woo_instance_id', string="Pickings")
    picking_count = fields.Integer(compute='_compute_all', string="Pickings Count")
    invoice_ids = fields.One2many('account.move', 'woo_instance_id', string="Invoices")
    invoice_count = fields.Integer(compute='_compute_all', string="Invoices Count")
    exported_product_count = fields.Integer(compute='_compute_all', string="Exported Products Count")
    ready_to_export_product_count = fields.Integer(compute='_compute_all',
                                                   string="Ready To Export Count")
    published_product_count = fields.Integer(compute='_compute_all', string="Published Count")
    unpublished_product_count = fields.Integer(compute='_compute_all', string="UnPublished Count")
    quotation_count = fields.Integer(compute='_compute_all', string="Quotations Count")
    order_ids = fields.One2many('sale.order', 'woo_instance_id',
                                domain=[('state', 'not in', ['draft', 'sent', 'cancel'])],
                                string="Sales Order")
    order_count = fields.Integer(compute='_compute_all', string="Sales Order Count")
    confirmed_picking_count = fields.Integer(compute='_compute_all', string="Confirm Pickings Counts")
    assigned_picking_count = fields.Integer(compute='_compute_all', string="Assigned Pickings Counts")
    partially_available_picking_count = fields.Integer(compute='_compute_all',
                                                       string="Partially Available Pickings Count")
    done_picking_count = fields.Integer(compute='_compute_all', string="Done Pickings Count")
    open_invoice_count = fields.Integer(compute='_compute_all', string="Open Invoices Count")
    paid_invoice_count = fields.Integer(compute='_compute_all', string="Paid Invoices Count")
    refund_invoice_count = fields.Integer(compute='_compute_all', string="Refund Invoices Count")

    user_ids = fields.Many2many('res.users', string='Responsible User')
    activity_type_id = fields.Many2one('mail.activity.type',
                                       string="Activity Type")
    date_deadline = fields.Integer('Deadline lead days',
                                   help="its add number of  days in schedule activity deadline date ")
    is_create_schedule_activity = fields.Boolean(string="Is Create Schedule Activity?", help="If "
                                                                                             "marked it will create a "
                                                                                             "schedule activity of "
                                                                                             "mismatch sales order in "
                                                                                             "the order queue.")
    active = fields.Boolean("Active", default=True)

    webhook_ids = fields.One2many("woo.webhook.ept", "instance_id")
    create_woo_product_webhook = fields.Boolean("Manage Products via Webhooks",
                                                help="If checked, it will create all product related webhooks.")
    create_woo_customer_webhook = fields.Boolean("Manage Customers via Webhooks",
                                                 help="If checked, it will create all customer related webhooks.")
    create_woo_order_webhook = fields.Boolean("Manage Orders via Webhooks",
                                              help="If checked, it will create all order related webhooks.")
    create_woo_coupon_webhook = fields.Boolean("Manage Coupons via Webhooks",
                                               help="If checked, it will create all coupon related webhooks.")

    weight_uom_id = fields.Many2one("uom.uom", string="Weight UoM",
                                    default=lambda self:self.env.ref("uom.product_uom_kgm"))

    _sql_constraints = [('unique_host', 'unique(woo_host)',
                         "Instance already exists for given host. Host must be Unique for the instance!")]

    def woo_action_archive(self):
        """
        This method used to archive or unarchive instances and also disable the cron job of
        related instances while archiving the instance.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 09-12-2019.
        :Task id: 158502
        """
        if self.active:
            self.active = False
            self.write({'state': 'not_confirmed'})
            auto_crons = self.env["ir.cron"].search(
                [("name", "ilike", self.name), ("active", "=", True)])
            if auto_crons:
                auto_crons.write({"active": False})
                self.woo_stock_auto_export = False
                self.auto_update_order_status = False
                self.auto_import_order = False
            webhooks = self.env["woo.webhook.ept"].search(
                [("instance_id", "=", self.id), ("status", "=", "active")])
            if webhooks:
                webhooks.toggle_status("paused")
            self.create_woo_product_webhook = False
            self.create_woo_order_webhook = False
            self.create_woo_customer_webhook = False
            self.create_woo_coupon_webhook = False
        else:
            self.active = True
            self.confirm()

    @api.model
    def create(self, vals):
        """
        Create pricelist and set that to instance.
        :param vals: Dict of instance
        :return: instance
        """
        if vals.get("woo_host").endswith('/'):
            vals["woo_host"] = vals.get("woo_host").rstrip('/')

        instance = super(woo_instance_ept, self).create(vals)
        instance.woo_set_current_currency_data()
        pricelist = instance.woo_create_pricelist()
        sales_channel = instance.create_sales_channel()
        global_channel = instance.create_global_channel()

        instance.write({
            'woo_pricelist_id': pricelist.id,
            'sales_team_id': sales_channel.id,
            'global_channel_id': global_channel.id
        })

        return instance

    def woo_create_pricelist(self):
        """
        Create price list for woocommerce instance
        :return: pricelist
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 18-11-2019.
        :Task id: 156886
        """
        pricelist_obj = self.env['product.pricelist']
        vals = {
            'name': "Woo {} Pricelist".format(self.name),
            'currency_id': self.woo_currency_id and self.woo_currency_id.id or False,
            "company_id": self.company_id.id
        }
        pricelist = pricelist_obj.create(vals)
        return pricelist

    def create_global_channel(self):
        """
        Creates new global channel for Woo instance.
        @author: Maulik Barad on Date 09-Jan-2019.
        """
        global_channel_obj = self.env['global.channel.ept']
        vals = {
            'name': self.name
        }
        return global_channel_obj.create(vals)

    def create_sales_channel(self):
        """
        Creates new sales team for Woo instance.
        @author: Maulik Barad on Date 09-Jan-2019.
        """
        crm_team_obj = self.env['crm.team']
        vals = {
            'name': self.name,
            'use_quotations': True
        }
        return crm_team_obj.create(vals)

    def woo_set_current_currency_data(self):
        """
        Set default instance currency according to woocommerce store currency
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 18-11-2019.
        :Task id: 156886
        """
        currency = self.woo_get_currency()
        self.woo_currency_id = currency and currency.id or self.env.user.currency_id.id or False
        return True

    @api.model
    def woo_get_currency(self):
        """
        Get currency from odoo according to woocommerce store currency.
        :return: currency
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 18-11-2019.
        :Task id: 156886
        """
        common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "woo.instance.ept"
        model_id = common_log_line_obj.get_model_id(model)
        currency_obj = self.env['res.currency']
        log_line_id = []
        response = self.woo_get_system_info()
        currency_code = ""
        currency_symbol = ""
        if not response:
            raise Warning("Json Error:\n The response is not coming in proper format from WooCommerce store.\n Please check the Store.")
        if self.woo_version == 'v3':
            currency_code = response.get('store').get('meta').get('currency', False)
            currency_symbol = response.get('store').get('meta').get('currency_format', False)
        elif self.woo_version == 'wc/v1':
            endpoints = response.get("routes").get("/wc/v1/orders").get("endpoints")
            for endpoint in endpoints:
                if endpoint.get("args").get("currency", False):
                    currency_code = endpoint.get("args").get("currency", False).get('default')
                    currency_symbol = True
                    break
        else:
            currency_code = response.get('settings').get('currency', False)
            currency_symbol = response.get('settings').get('currency_symbol', False)

        if not currency_code:
            log_id = common_log_line_obj.create({
                'model_id': model_id,
                'message': "Import Woo System Status \nCurrency Code Not Received in Response"
            })
            log_line_id.append(log_id.id)
        if not currency_symbol:
            log_id = common_log_line_obj.create({
                'model_id': model_id,
                'message': "Import Woo System Status \nCurrency Symbol Not Received in Response"
            })
            log_line_id.append(log_id.id)

        currency = currency_obj.search([
            ('name', '=', currency_code)
        ])

        if not currency and self.woo_auto_active_currency:
            currency = currency_obj.search([
                ('name', '=', currency_code),
                ('active', '!=', True)
            ])
            currency.active = True
        if not currency:
            raise Warning(
                "Currency {} not found in odoo.\nPlease make sure currency record is created for {} and is in active "
                "state.".format(
                    currency_code, currency_code))

        if log_line_id:
            common_log_id = common_log_obj.create({
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': self.id,
                'active': True,
            })
            common_log_line_obj.browse(log_line_id).write(
                {'log_line_id': common_log_id and common_log_id.id or False})
        return currency

    def woo_get_system_info(self):
        """
        Get system information like store currency, configurations of woocommerce etc.
        :return: List
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 18-11-2019.
        :Task id: 156886
        """
        wcapi = self.woo_connect()
        common_log_line_obj = self.env["common.log.lines.ept"]
        log_line_id = []
        model = "woo.instance.ept"
        model_id = common_log_line_obj.get_model_id(model)
        if self.woo_version in ['v3', 'wc/v1']:
            res = wcapi.get("")
        else:
            res = wcapi.get("system_status")
        if not isinstance(res, requests.models.Response):
            log_id = common_log_line_obj.create({
                'model_id': model_id,
                'message': "Import Woo System Status \nResponse is not in proper format :: %s" % (
                    res)
            })
            log_line_id.append(log_id.id)
        if res.status_code not in [200, 201]:
            message = "Error in Import Woo System Status %s" % res.content
            log_id = common_log_line_obj.create({
                'model_id': model_id,
                'message': message
            })
            log_line_id.append(log_id.id)
        try:
            response = res.json()
        except Exception as e:
            log_id = common_log_line_obj.create({
                'model_id': model_id,
                'message': "Json Error : While import system status from WooCommerce for self %s. \n%s" % (
                    self.name, e)
            })
            log_line_id.append(log_id.id)
        if self.woo_version == 'v3':
            errors = response.get('errors', '')
            if errors:
                message = errors[0].get('message')
                log_id = common_log_line_obj.create({
                    'model_id': model_id,
                    'message': message
                })
                log_line_id.append(log_id.id)
        if log_line_id:
            common_log_obj = self.env["common.log.book.ept"]
            common_log_id = common_log_obj.create({
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': self.id,
                'active': True,
            })
            common_log_line_obj.browse(log_line_id).write(
                {'log_line_id': common_log_id and common_log_id.id or False})
            return []
        return response

    @api.model
    def woo_connect(self):
        """
        Creates connection for given instance of Woo.
        @author: Maulik Barad on Date 09-Jan-2019.
        """
        host = self.woo_host
        consumer_key = self.woo_consumer_key
        consumer_secret = self.woo_consumer_secret
        wp_api = False if self.woo_version == 'v3' else True
        wcapi = woocommerce.api.API(url=host, consumer_key=consumer_key,
                                    consumer_secret=consumer_secret, verify_ssl=self.woo_verify_ssl,
                                    wp_api=wp_api,
                                    version=self.woo_version, query_string_auth=True)
        return wcapi

    def confirm(self):
        """
        Performs needed operations for instance after its creation.
        @author: Maulik Barad on Date 09-Jan-2019.
        """
        wcapi = self.woo_connect()
        r = wcapi.get("products", params={"_fields": "id"})
        if not isinstance(r, requests.models.Response):
            raise Warning(_("Response is not in proper format :: %s" % r))
        if r.status_code != 200:
            raise Warning(_("%s\n%s" % (r.status_code, r.reason)))
        else:
            """
            When there is case of full discount, customer do not need to pay or select any payment
            method for that order.
            So, creating this type of payment method for applying the auto workflow and picking
            policy in order.
            """
            no_payment_method = self.env['woo.payment.gateway'].search([
                ("code", "=", "no_payment_method"), ("woo_instance_id", "=", self.id)])
            if not no_payment_method:
                self.env['woo.payment.gateway'].create({"name":"No Payment Method",
                                                        "code":"no_payment_method",
                                                        "woo_instance_id":self.id})
            self.woo_create_financial_status('paid')
            self.woo_create_financial_status('not_paid')
            self.write({'state': 'confirmed'})
        return True

    def woo_create_financial_status(self, financial_status):
        """
        Creates financial status for all payment methods of Woo instance.
        @param financial_status: Status as paid or not paid.
        @return: Boolean
        """
        payment_methods = self.env['woo.payment.gateway'].search(
            [('woo_instance_id', '=', self.id)])
        financial_status_obj = self.env["woo.sale.auto.workflow.configuration"]
        auto_workflow_record = self.env.ref("auto_invoice_workflow_ept.automatic_validation_ept")
        for payment_method in payment_methods:
            domain = [('woo_instance_id', '=', self.id),
                      ('woo_payment_gateway_id', '=', payment_method.id),
                      ('woo_financial_status', '=', financial_status)]
            existing_financial_status = financial_status_obj.search(domain).ids

            if existing_financial_status:
                continue

            vals = {
                'woo_instance_id': self.id,
                'woo_auto_workflow_id': auto_workflow_record.id,
                'woo_payment_gateway_id': payment_method.id,
                'woo_financial_status': financial_status
            }
            financial_status_obj.create(vals)
        return True

    def action_redirect_to_ir_cron(self):
        """
        This method is used for redirect to scheduled action tree view and filtered only WooCommerce crons.
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 16-11-2019.
        :Task id: 156886
        :return: action
        """
        action = self.env.ref('base.ir_cron_act').read()[0]
        action['domain'] = [('name', 'ilike', self.name)]
        return action

    def refresh_webhooks(self, webhooks=False):
        """
        This method refreshes all webhooks for current instance.
        @author: Maulik Barad on Date 19-Dec-2019.
        """
        if not webhooks:
            webhooks = self.webhook_ids
        for webhook in webhooks:
            webhook.get_webhook()
        _logger.info("Webhooks are refreshed of instance '{0}'.".format(self.name))
        return True

    def configure_woo_product_webhook(self):
        """
        Creates or activates all product related webhooks, when it is True.
        Pauses all product related webhooks, when it is False.
        @author: Maulik Barad on Date 06-Jan-2019.
        """
        topic_list = ["product.created", "product.updated", "product.deleted", "product.restored"]
        self.configure_webhooks(topic_list)

    def configure_woo_customer_webhook(self):
        """
        Creates or activates all product related webhooks, when it is True.
        Pauses all product related webhooks, when it is False.
        @author: Maulik Barad on Date 06-Jan-2019.
        """
        topic_list = ["customer.created", "customer.updated", "customer.deleted"]
        self.configure_webhooks(topic_list)

    def configure_woo_order_webhook(self):
        """
        Creates or activates all product related webhooks, when it is True.
        Pauses all product related webhooks, when it is False.
        @author: Maulik Barad on Date 06-Jan-2019.
        """
        topic_list = ["order.created", "order.updated", "order.deleted"]
        self.configure_webhooks(topic_list)

    def configure_woo_coupon_webhook(self):
        """
        Creates or activates all product related webhooks, when it is True.
        Pauses all product related webhooks, when it is False.
        @author: Maulik Barad on Date 06-Jan-2019.
        """
        topic_list = ["coupon.created", "coupon.updated", "coupon.deleted", "coupon.restored"]
        self.configure_webhooks(topic_list)

    def configure_webhooks(self, topic_list):
        """
        Creates or activates all webhooks as per topic list, when it is True.
        Pauses all product related webhooks, when it is False.
        """
        webhook_obj = self.env["woo.webhook.ept"]

        resource = topic_list[0].split('.')[0]
        instance_id = self.id
        available_webhooks = webhook_obj.search([("topic", "in", topic_list), ("instance_id", "=", instance_id)])

        self.refresh_webhooks(available_webhooks)

        if getattr(self, "create_woo_%s_webhook" % resource):
            if available_webhooks:
                available_webhooks.toggle_status("active")
                _logger.info("{0} Webhooks are activated of instance '{1}'.".format(resource, self.name))
                topic_list = list(set(topic_list) - set(available_webhooks.mapped("topic")))

            for topic in topic_list:
                webhook_obj.create({"name": self.name + "_" + topic.replace(".", "_"),
                                    "topic": topic, "instance_id": instance_id})
                _logger.info("Webhook for '{0}' of instance '{1}' created.".format(topic, self.name))
        else:
            if available_webhooks:
                available_webhooks.toggle_status("paused")
                _logger.info("{0} Webhooks are paused of instance '{1}'.".format(resource, self.name))
