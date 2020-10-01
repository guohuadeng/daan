import requests
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_woo_customer = fields.Boolean(string="Is Woo Customer?",
                                     help="Used for identified that the customer is imported from WooCommerce store.")

    def woo_import_all_customers(self, wcapi, instance, common_log_id, page):
        """
        Call API for get customers according to page.
        :param wcapi: connection object
        :param instance: Instance object
        :param common_log_id: common log book id
        :param page: page no which we want to get
        :return: Dict
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "woo.instance.ept"
        model_id = common_log_line_obj.get_model_id(model)
        if instance.woo_version in ['wc/v1', 'wc/v2', 'wc/v3']:
            res = wcapi.get('customers', params={"per_page": 100, 'page': page})
        else:
            res = wcapi.get('customers?filter[limit]=100&page=%s' % (page))
        if not isinstance(res, requests.models.Response):
            common_log_line_obj.create({
                'log_line_id': common_log_id and common_log_id.id or False,
                'model_id': model_id,
                'message': "Import all customers \nresponse is not in proper format :: %s" % (res)
            })
            return []
        if res.status_code not in [200, 201]:
            message = "Error in Import All Customers %s" % (res.content)
            common_log_line_obj.create({
                'log_line_id': common_log_id and common_log_id.id or False,
                'model_id': model_id,
                'message': message
            })
            return []
        try:
            response = res.json()
        except Exception as e:
            common_log_line_obj.create({
                'log_line_id': common_log_id and common_log_id.id or False,
                'model_id': model_id,
                'message': "Json Error : While import customers from WooCommerce for instance %s. \n%s" % (
                    instance.name, e),
            })
            return []
        if instance.woo_version == 'v3':
            errors = response.get('errors', '')
            if errors:
                message = errors[0].get('message')
                common_log_line_obj.create({
                    'log_line_id': common_log_id and common_log_id.id or False,
                    'model_id': model_id,
                    'message': message
                })
                return
            return response.get('customers')
        else:
            return response

    @api.model
    def woo_get_customers(self, instance=False):
        """
        Call API for get customers from WooCommerce.
        :param instance: Object of instance
        :return: Dict
        """
        common_log_obj = self.env["common.log.book.ept"]
        common_log_id = common_log_obj.create({
            'type': 'import',
            'module': 'woocommerce_ept',
            'woo_instance_id': instance.id,
            'active': True,
        })
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "res.partner"
        model_id = common_log_line_obj.get_model_id(model)

        wcapi = instance.woo_connect()
        if instance.woo_version == 'wc/v3':
            response = wcapi.get('customers', params={"per_page": 100})
        else:
            # Need to check
            response = wcapi.get('customers?filter[limit]=-1')
        if not isinstance(response, requests.models.Response):
            common_log_line_obj.create({
                'log_line_id': common_log_id and common_log_id.id or False,
                'model_id': model_id,
                'message': "Import Customers \nResponse is not in proper format :: %s" % (response)
            })
            return []
        if response.status_code not in [200, 201]:
            common_log_line_obj.create({
                'log_line_id': common_log_id and common_log_id.id or False,
                'model_id': model_id,
                'message': "Error in Import Customers %s" % (response.content)
            })
            return []
        customers = []
        if instance.woo_version == 'v3':
            try:
                customers = response.json().get('customers')
            except Exception as e:
                common_log_line_obj.create({
                    'log_line_id': common_log_id and common_log_id.id or False,
                    'model_id': model_id,
                    'message': "Json Error : While import Customers from WooCommerce for instance %s. \n%s" % (
                        instance.name, e)
                })
                return []
        else:
            try:
                customer_response = response.json()
            except Exception as e:
                common_log_line_obj.create({
                    'log_line_id': common_log_id and common_log_id.id or False,
                    'model_id': model_id,
                    'message': "Json Error : While import Customers from WooCommerce for instance %s. \n%s" % (
                        instance.name, e),
                })
                return []
            customers = customers + customer_response
            total_pages = response.headers.get('X-WP-TotalPages')
            if int(total_pages) >= 2:
                for page in range(2, int(total_pages) + 1):
                    customers = customers + self.woo_import_all_customers(wcapi, instance,
                                                                          common_log_id, page)
        if not common_log_id.log_lines:
            common_log_id.sudo().unlink()
        return customers

    def woo_create_or_get_child_partner(self, partner_vals, key_list, parent_id, type):
        partner = self._find_partner(partner_vals, key_list, [('parent_id', '=', parent_id)])
        if partner:
            return partner
        else:
            partner = self._find_partner(partner_vals, key_list)
            if partner:
                return partner
            else:
                partner_vals.update({
                    'parent_id': parent_id,
                    'type': type,
                    'is_company': False,
                })
                partner = self.create(partner_vals)
                return partner

    def woo_create_or_update_customer(self, woo_cust_id, vals, is_company=False, parent_id=False, type=False,
                                      instance=False):
        """
        Create partner if doesn't exists else it'll update
        :param woo_cust_id: woocommerce customer id
        :param vals: Dict of billing/shipping address
        :param parent_id: parent id of customer
        :param type: for create shipping address
        :param instance: Object of instance
        :return: partner
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 30-10-2019.
        :Task id: 156886
        """
        first_name = vals.get("first_name")
        last_name = vals.get("last_name")
        if not first_name and not last_name:
            return False

        name = "%s %s" % (first_name, last_name)
        company_name = vals.get("company")

        email = vals.get("email")
        phone = vals.get("phone")
        address1 = vals.get("address_1")
        address2 = vals.get("address_2")
        city = vals.get("city")
        zip = vals.get("postcode")
        state_name = vals.get("state")
        country_name = vals.get("country")

        woo_instance_id = instance.id
        woo_customer_id = "%s" % (woo_cust_id) if woo_cust_id else False
        country = self.get_country(country_name)
        state_obj = self.env['res.country.state']
        if not country:
            state = state_obj.search(["|", ('code', '=', state_name), ('name', '=', state_name)], limit=1)
        else:
            state = state_obj.search(
                ["|", ('code', '=', state_name), ('name', '=', state_name), ('country_id', '=', country.id)], limit=1)

        woo_partner_obj = self.env['woo.res.partner.ept']
        partner_vals = {
            'email': email or False,
            'name': name,
            'phone': phone,
            'street': address1,
            'street2': address2,
            'city': city,
            'zip': zip,
            'state_id': state and state.id or False,
            'country_id': country and country.id or False,
            'is_company': is_company,
            'lang': instance.woo_lang_id.code,
            'company_id': instance.company_id.id,
        }
        key_list = ['name', 'street', 'street2', 'city', 'zip', 'state_id', 'country_id', 'email', 'phone']

        if is_company:
            partner = woo_partner_obj.search(
                [("woo_customer_id", "=", woo_customer_id), ("woo_instance_id", "=", woo_instance_id)],
                limit=1) if woo_customer_id else False
            if partner:
                partner = partner.partner_id
                if not parent_id:
                    parent_id = partner.id
                return self.woo_create_or_get_child_partner(partner_vals, key_list, parent_id, 'invoice')
            else:
                partner = self._find_partner(partner_vals, key_list, [('parent_id', '=', False)])
                woo_partner_values = {
                    'woo_customer_id': woo_customer_id,
                    'woo_instance_id': woo_instance_id,
                    'woo_company_name_ept': company_name,
                }
                if partner:
                    partner.write({'is_company': True, 'is_woo_customer': True})
                    woo_partner_values.update({'partner_id':partner.id})
                else:
                    # There are chances a partner may already exist
                    # In that case we need to decide whether to associate that partner with
                    # WooCustomer id and WooInstance id in new normalized table(woo_res_partner_ept)
                    partner = self.search([("email", "=", email), ('parent_id', '=', False)], limit=1)
                    if partner:
                        parent_id = partner.id
                        partner.write({'is_company': True, 'is_woo_customer': True})
                        partner_vals.update({'parent_id': parent_id, 'is_company': False, 'type': 'invoice'})
                        partner = self.create(partner_vals)
                        woo_partner_values.update({'partner_id': parent_id})
                    else:
                        partner_vals.update({
                            'customer_rank': 1,
                            'is_woo_customer': True
                        })
                        partner = self.create(partner_vals)
                        woo_partner_values.update({'partner_id': partner.id})

                self.create_woo_res_partner_ept(woo_partner_obj, woo_partner_values)
                return partner
        else:
            return self.woo_create_or_get_child_partner(partner_vals, key_list, parent_id, type)

    def create_woo_res_partner_ept(self, woo_partner_obj, woo_partner_values):
        """
        Create partner in woo.res.partner.ept
        :param woo_partner_obj: Object of woo_res_partner_ept
        :param woo_partner_values: Dict of woo partner
        """
        woo_partner_obj.create({
            'partner_id': woo_partner_values.get('partner_id'),
            'woo_customer_id': woo_partner_values.get('woo_customer_id'),
            'woo_instance_id': woo_partner_values.get('woo_instance_id'),
            'woo_company_name_ept': woo_partner_values.get('woo_company_name_ept'),
        })
