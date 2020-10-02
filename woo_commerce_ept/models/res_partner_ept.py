from odoo import models, fields, api, _
import json
from datetime import datetime


class WooResPartnerEpt(models.Model):
    _name = "woo.res.partner.ept"
    _description = "Manage WooCommerce Customers"

    partner_id = fields.Many2one("res.partner", "Customer", ondelete='cascade')
    woo_customer_id = fields.Char(string="Woo Customer Id", help="WooCommerce customer id.")
    woo_instance_id = fields.Many2one("woo.instance.ept", "WooCommerce Instances",
                                      help="Instance id managed for identified that customer associated with which instance.")
    woo_company_name_ept = fields.Char(string="Woo Company Name")

    def find_customer(self, instance, customer):
        """check_partner_contact_address
        :param instance: Object of instance
        :param customer: Response of the customer
        :return: It will return the odoo and woo customer object
        """
        woo_partner = self.search([('woo_customer_id', '=', customer.get('id')),
                                   ('woo_instance_id', '=', instance.id)]) if customer.get(
            'id') else False
        if not woo_partner:
            odoo_partner = self.env['res.partner'].search(
                [('email', '=', customer.get('email')), ('parent_id', '=', False)], limit=1)
        else:
            odoo_partner = woo_partner.partner_id
        return woo_partner, odoo_partner

    def process_customers(self, instance, response, is_shipping_address, partner=False):
        """
        :param instance: Object of instance
        :param customer_queue: Object of customer_queue
        :param is_shipping_address: It contain Either True or False
        :return: True if successfully process complete
        @author: Dipak Gogiya on Date 01-Jan-2020.
        """
        if not partner:
            partner_vals = {
                'name': response.get('username'),
                'email': response.get('email'),
                'customer_rank': 1,
                'is_woo_customer': True,
                'type': 'invoice',
                'company_type': 'company'
                }
            partner = self.env['res.partner'].create(partner_vals)
        if partner:
            if is_shipping_address:
                parent_id = partner.id
                if partner.parent_id:
                    parent_id = partner.parent_id.id
                shipping_partner = self.env['res.partner'].woo_create_or_update_customer(False,
                                                                                         response.get(
                                                                                             'shipping'),
                                                                                         False,
                                                                                         parent_id,
                                                                                         'delivery',
                                                                                         instance)
                if not shipping_partner.parent_id:
                    shipping_partner.write({'parent_id': partner.id})
            woo_partner_values = {
                'woo_customer_id': response.get('id', False),
                'woo_instance_id': instance.id,
                'woo_company_name_ept': response.get('company'),
                'partner_id': partner.id
                }
            self.create(woo_partner_values)
        return True

    def check_partner_contact_address(self, response, partner, woo_partner, instance,
                                      is_shipping_address):
        """
        This method is Check the address is set or not in res partner
        :param customer_queue: Object of customer_queue
        :param partner: Object of Res Partner
        :param instance: Object of instance
        :is_shipping_address: It contain Either True or False and its type is list
        :is_billing_address: It contain Either True or False and its type is list
        :return: It will return the partner and address dictionary
        @author: Dipak Gogiya on Date 01-Jan-2020.
        """
        partner_obj = self.env['res.partner'].sudo()
        if not woo_partner:
            woo_partner_values = {
                'woo_customer_id': response.get('id', False),
                'woo_instance_id': instance.id,
                'woo_company_name_ept': response.get('company'),
                'partner_id': partner.id
                }
            self.create(woo_partner_values)
        if partner:
            if is_shipping_address:
                parent_id = partner.id
                if partner.parent_id:
                    parent_id = partner.parent_id.id
                shipping_partner = partner_obj.woo_create_or_update_customer(False,
                                                                             response.get('shipping'),
                                                                             False, parent_id,
                                                                             'delivery', instance)
                if not shipping_partner.parent_id:
                    shipping_partner.write({'parent_id': partner.id})
        return True
