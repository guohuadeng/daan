import logging
import requests

from .. import woocommerce
from ..wordpress_xmlrpc import base, media
from ..wordpress_xmlrpc.exceptions import InvalidCredentialsError
from ..img_upload.img_file_upload import SpecialTransport

from odoo import models, fields, api, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import Warning

_logger = logging.getLogger("WooCommerce")


class WooInstanceConfig(models.TransientModel):
    _name = 'res.config.woo.instance'
    _description = "WooCommerce Instance Creation"

    @api.model
    def _woo_tz_get(self):
        """
        Gives all timezones from base.
        @author: Maulik Barad on Date 18-Nov-2019.
        @return: Calls base method for all timezones.
        """
        return _tz_get(self)

    name = fields.Char("Instance Name")
    woo_consumer_key = fields.Char("Consumer Key", required=True,
                                   help="Login into WooCommerce site,Go to Admin Panel >> WooCommerce >> Settings >> "
                                        "Advanced >> REST API >> Click on Add Key")
    woo_consumer_secret = fields.Char("Consumer Secret", required=True,
                                      help="Login into WooCommerce site,Go to Admin Panel >> WooCommerce >> Settings "
                                           ">> Advanced >> REST API >> Click on Add Key")
    woo_host = fields.Char("Host", required=True, help="URL of your WooCommerce Store.")
    woo_country_id = fields.Many2one('res.country', string="Country", required=True)
    woo_is_image_url = fields.Boolean("Is Image URL?",
                                      help="Check this if you use Images from URL\nKepp as it is if you use Product "
                                           "images")
    woo_admin_username = fields.Char("Username",
                                     help="WooCommerce username for exporting Image files.")
    woo_admin_password = fields.Char("Password",
                                     help="WooCommerce password for exporting Image files.")
    woo_version = fields.Selection([("v3", "Below 2.6"),
                                    ("wc/v1", "2.6 To 2.9"),
                                    ("wc/v2", "3.0 To 3.4"),
                                    ("wc/v3", "3.5+")],
                                   default="wc/v3", string="WooCommerce Version",
                                   help="Set the appropriate WooCommerce Version you are using currently or\n"
                                        "Login into WooCommerce site,Go to Admin Panel >> Plugins")
    woo_verify_ssl = fields.Boolean("Verify SSL", default=False,
                                    help="Check this if your WooCommerce site is using SSL "
                                         "certificate")
    store_timezone = fields.Selection("_woo_tz_get", help="Timezone of Store for requesting data.")

    def woo_test_connection(self):
        host = self.woo_host
        consumer_key = self.woo_consumer_key
        consumer_secret = self.woo_consumer_secret
        verify_ssl = self.woo_verify_ssl
        version = self.woo_version
        wp_api = False if version == 'v3' else True
        wcapi = woocommerce.api.API(url=host, consumer_key=consumer_key,
                                    consumer_secret=consumer_secret, verify_ssl=verify_ssl,
                                    wp_api=wp_api,
                                    version=version, query_string_auth=True)
        r = wcapi.get("products", params={"_fields": "id"})
        if not isinstance(r, requests.models.Response):
            raise Warning(_("Response is not in proper format :: %s" % (r)))
        if r.status_code != 200:
            raise Warning(_("%s\n%s" % (r.status_code, r.reason)))

        if self.woo_admin_username and self.woo_admin_password:
            """Checking if username and password are correct or not."""
            client = base.Client('%s/xmlrpc.php' % (host), self.woo_admin_username, self.woo_admin_password, transport=SpecialTransport())
            try:
                client.call(media.UploadFile(""))
            except InvalidCredentialsError as error:
                raise Warning(_("%s" % (error)))
            except Exception as error:
                _logger.info(_("%s") % (error))

        instance = self.env['woo.instance.ept'].create({'name': self.name,
                                                        'woo_consumer_key': consumer_key,
                                                        'woo_consumer_secret': consumer_secret,
                                                        'woo_host': host,
                                                        'woo_verify_ssl': verify_ssl,
                                                        'woo_country_id': self.woo_country_id.id,
                                                        'woo_is_image_url': self.woo_is_image_url,
                                                        'woo_version': version,
                                                        "store_timezone": self.store_timezone,
                                                        'woo_admin_username': self.woo_admin_username,
                                                        'woo_admin_password': self.woo_admin_password,
                                                        })
        if instance.woo_version in ["wc/v2", "wc/v3"]:
            self.env['woo.payment.gateway'].woo_get_payment_gateway(instance)
        instance.confirm()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    woo_instance_id = fields.Many2one('woo.instance.ept', 'Woo Instance',
                                      help="Select WooCommerce Instance that you want to configure.")
    woo_warehouse_id = fields.Many2one('stock.warehouse', string="Woo Warehouse",
                                       domain="[('company_id','=',woo_company_id)]",
                                       help="Stock Management, Order Processing & Fulfillment will be carried out "
                                            "from this warehouse.")
    woo_company_id = fields.Many2one('res.company', string='Woo Company',
                                     default=lambda self:self.env.company,
                                     help="Orders and Invoices will be generated of this company.")

    woo_lang_id = fields.Many2one('res.lang', string='Woo Instance Language',
                                  help="Select language for WooCommerce customer.")
    woo_stock_field = fields.Many2one('ir.model.fields', string='Woo Stock Field',
                                      help="Choose the field by which you want to update the stock in WooCommerce "
                                           "based on Quantity on Hand or Forecasted Quantity (Onhand - Outgoing).")

    woo_pricelist_id = fields.Many2one('product.pricelist', string='Woo Instance Pricelist',
                                       help="Product Price will be stored in this pricelist in Odoo.")
    woo_payment_term_id = fields.Many2one('account.payment.term',
                                          string='Woo Instance Payment Term',
                                          help="Select the condition of payment for invoice.")
    woo_auto_import_product = fields.Boolean(string="Automatically Create Odoo Product If Not Found?")
    woo_sync_price_with_product = fields.Boolean("Woo Sync/Import Product Price?",
                                                 help="Check if you want to import price along with"
                                                      " products", default=False)
    woo_sync_images_with_product = fields.Boolean("Woo Sync/Import Images?",
                                                  help="Check if you want to import images along "
                                                       "with products.", default=False)
    # For Orders.
    woo_import_order_status_ids = fields.Many2many('import.order.status.ept',
                                                   'woo_config_settings_order_status_rel',
                                                   'woo_config_id', 'status_id',
                                                   help="Select Order Status of the type of orders"
                                                        "you want to import from WooCommerce.")
    woo_last_order_import_date = fields.Datetime(string="Last Order Import Date",
                                                 help="This is the date when last order you have imported in "
                                                      "Odoo.\nSystem will set this date in 'From date' while import "
                                                      "order process.")
    woo_sales_team_id = fields.Many2one('crm.team',
                                        help="Choose Sales Team that handles the order you import.")
    woo_global_channel_id = fields.Many2one('global.channel.ept')
    woo_custom_order_prefix = fields.Boolean("Use Custom Order Prefix",
                                             help="""True:Use Custom Order Prefix,
                                             False:Default Sale Order Prefix""")
    woo_order_prefix = fields.Char(size=10, help="Custom order prefix for Woocommerce orders.")
    woo_apply_tax = fields.Selection(
        [("odoo_tax", "Odoo Default Tax"), ("create_woo_tax", "Create new tax if not found")],
        default="create_woo_tax", copy=False,
        help=""" For Woocommerce Orders :- \n
        1) Odoo Default Tax Behaviour - The Taxes will be set based on Odoo's default functional behavior i.e. based 
        on Odoo's Tax and Fiscal Position configurations.\n
        2) Create New Tax If Not Found - System will search the tax data received from Woocommerce in Odoo, 
        will create a new one if it fails in finding it."""
    )
    woo_invoice_tax_account_id = fields.Many2one('account.account', string="Invoice Tax Account")
    woo_credit_note_tax_account_id = fields.Many2one('account.account',
                                                     string="Credit Note Tax Account")
    woo_user_ids = fields.Many2many('res.users', string="Responsible Users",
                                    help="To whom the activities will be assigned.")
    woo_activity_type_id = fields.Many2one('mail.activity.type', string="Activity Type")
    woo_date_deadline = fields.Integer('Deadline Lead Days',
                                       help="Days, that will be added in Schedule activity as Deadline days.")
    woo_is_create_schedule_activity = fields.Boolean(string="Is Create Schedule Activity?",
                                                     help="If marked, it will create a schedule activity of mismatch "
                                                          "details of critical situations.")
    create_woo_product_webhook = fields.Boolean("Manage Products via Webhooks",
                                                help="True : It will create all product related webhooks.\nFalse : "
                                                     "All product related webhooks will be deactivated.")
    create_woo_customer_webhook = fields.Boolean("Manage Customers via Webhooks",
                                                 help="True : It will create all customer related webhooks.\nFalse : "
                                                      "All customer related webhooks will be deactivated.")
    create_woo_order_webhook = fields.Boolean("Manage Orders via Webhooks",
                                              help="True : It will create all order related webhooks.\nFalse : All "
                                                   "order related webhooks will be deactivated.")
    create_woo_coupon_webhook = fields.Boolean("Manage Coupons via Webhooks",
                                               help="True : It will create all coupon related webhooks.\nFalse : All "
                                                    "coupon related webhooks will be deactivated.")
    woo_attribute_type = fields.Selection([("select", "Select"), ("text", "Text")],
                                          string="Attribute Type For Export Operation",
                                          default="select")
    woo_weight_uom_id = fields.Many2one("uom.uom", string="WooCommerce Weight Unit",
                                      domain=[('category_id.measure_type', '=', 'weight')])
    woo_set_sales_description_in_product = fields.Boolean("Use Sales Description of Odoo Product",
                                                          config_parameter="woo_commerce_ept.set_sales_description")

    @api.model
    def create(self, vals):
        if not vals.get('company_id'):
            vals.update({'company_id': self.env.company.id})
        res = super(ResConfigSettings, self).create(vals)
        return res

    @api.onchange('woo_instance_id')
    def onchange_woo_instance_id(self):
        instance = self.woo_instance_id or False

        if instance:
            self.woo_lang_id = instance.woo_lang_id and instance.woo_lang_id.id or False
            self.woo_stock_field = instance.woo_stock_field and instance.woo_stock_field.id or False
            self.woo_warehouse_id = instance.woo_warehouse_id and instance.woo_warehouse_id.id or False
            self.woo_pricelist_id = instance.woo_pricelist_id and instance.woo_pricelist_id.id or False
            self.woo_payment_term_id = instance.woo_payment_term_id and instance.woo_payment_term_id.id or False
            self.woo_auto_import_product = instance.auto_import_product
            self.woo_sync_price_with_product = instance.sync_price_with_product or False
            self.woo_sync_images_with_product = instance.sync_images_with_product or False
            self.woo_company_id = instance.company_id and instance.company_id.id or False

            self.woo_import_order_status_ids = instance.import_order_status_ids.ids
            self.woo_last_order_import_date = instance.last_order_import_date
            self.woo_sales_team_id = instance.sales_team_id
            self.woo_global_channel_id = instance.global_channel_id
            self.woo_auto_import_product = instance.auto_import_product
            self.woo_custom_order_prefix = instance.custom_order_prefix
            self.woo_order_prefix = instance.order_prefix
            self.woo_apply_tax = instance.apply_tax
            self.woo_invoice_tax_account_id = instance.invoice_tax_account_id
            self.woo_credit_note_tax_account_id = instance.credit_note_tax_account_id
            self.woo_user_ids = instance.user_ids or False
            self.woo_activity_type_id = instance.activity_type_id
            self.woo_date_deadline = instance.date_deadline
            self.woo_is_create_schedule_activity = instance.is_create_schedule_activity

            self.create_woo_product_webhook = instance.create_woo_product_webhook
            self.create_woo_customer_webhook = instance.create_woo_customer_webhook
            self.create_woo_order_webhook = instance.create_woo_order_webhook
            self.create_woo_coupon_webhook = instance.create_woo_coupon_webhook

            self.woo_attribute_type = instance.woo_attribute_type
            self.woo_weight_uom_id = instance.weight_uom_id

    @api.onchange('woo_company_id')
    def onchange_woo_company_id(self):
        """
        When company changes of instances, we will make warehouse field blank.
        """
        self.woo_warehouse_id = False

    def execute(self):
        instance = self.woo_instance_id
        values = {}
        res = super(ResConfigSettings, self).execute()
        if instance:
            values['woo_lang_id'] = self.woo_lang_id and self.woo_lang_id.id or False
            values['woo_stock_field'] = self.woo_stock_field and self.woo_stock_field.id or False
            values['woo_warehouse_id'] = self.woo_warehouse_id and self.woo_warehouse_id.id or False
            values['woo_pricelist_id'] = self.woo_pricelist_id and self.woo_pricelist_id.id or False
            values['woo_payment_term_id'] = self.woo_payment_term_id and self.woo_payment_term_id.id or False
            values['auto_import_product'] = self.woo_auto_import_product
            values['sync_price_with_product'] = self.woo_sync_price_with_product or False
            values['sync_images_with_product'] = self.woo_sync_images_with_product or False
            values['company_id'] = self.woo_company_id and self.woo_company_id.id or False

            values['import_order_status_ids'] = [(6, 0, self.woo_import_order_status_ids.ids)]
            values['last_order_import_date'] = self.woo_last_order_import_date or False
            values['sales_team_id'] = self.woo_sales_team_id or False
            values['global_channel_id'] = self.woo_global_channel_id or False
            values['auto_import_product'] = self.woo_auto_import_product or False
            values['custom_order_prefix'] = self.woo_custom_order_prefix or False
            values['order_prefix'] = self.woo_order_prefix or False
            values["apply_tax"] = self.woo_apply_tax
            values["invoice_tax_account_id"] = self.woo_invoice_tax_account_id
            values["credit_note_tax_account_id"] = self.woo_credit_note_tax_account_id
            values["activity_type_id"] = self.woo_activity_type_id and \
                                      self.woo_activity_type_id.id or False
            values["date_deadline"] = self.woo_date_deadline or False
            values.update({'user_ids': [(6, 0, self.woo_user_ids.ids)]})
            values['is_create_schedule_activity'] = self.woo_is_create_schedule_activity

            values["create_woo_product_webhook"] = self.create_woo_product_webhook
            values["create_woo_customer_webhook"] = self.create_woo_customer_webhook
            values["create_woo_order_webhook"] = self.create_woo_order_webhook
            values["create_woo_coupon_webhook"] = self.create_woo_coupon_webhook

            values["woo_attribute_type"] = self.woo_attribute_type
            values["weight_uom_id"] = self.woo_weight_uom_id

            product_webhook_changed = customer_webhook_changed = order_webhook_changed = coupon_webhook_changed = False
            if instance.create_woo_product_webhook != self.create_woo_product_webhook:
                product_webhook_changed = True
            if instance.create_woo_customer_webhook != self.create_woo_customer_webhook:
                customer_webhook_changed = True
            if instance.create_woo_order_webhook != self.create_woo_order_webhook:
                order_webhook_changed = True
            if instance.create_woo_coupon_webhook != self.create_woo_coupon_webhook:
                coupon_webhook_changed = True

            instance.write(values)

            if product_webhook_changed:
                instance.configure_woo_product_webhook()
            if customer_webhook_changed:
                instance.configure_woo_customer_webhook()
            if order_webhook_changed:
                instance.configure_woo_order_webhook()
            if coupon_webhook_changed:
                instance.configure_woo_coupon_webhook()

        return res
