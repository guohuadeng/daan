import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta

import requests

from odoo import models, fields, api
from ..img_upload import img_file_upload

_logger = logging.getLogger("Woo")


class WooProductTemplateEpt(models.Model):
    _name = "woo.product.template.ept"
    _order = 'product_tmpl_id'
    _description = "WooCommerce Product Template"

    @api.depends('woo_product_ids.exported_in_woo', 'woo_product_ids.variant_id')
    def _compute_total_sync_variants(self):
        """
        :param : self :- It is the browsable object of woo product template class
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        woo_product_obj = self.env['woo.product.product.ept']
        for template in self:
            variants = woo_product_obj.search(
                [('id', 'in', template.woo_product_ids.ids), ('exported_in_woo', '=', True),
                 ('variant_id', '!=', False)])
            template.total_sync_variants = len(variants)

    name = fields.Char("Name", translate=True)
    woo_instance_id = fields.Many2one("woo.instance.ept", "Instance", required=1)
    product_tmpl_id = fields.Many2one("product.template", "Product Template", required=1,
                                      ondelete="cascade")
    active = fields.Boolean("Active", default=True)
    woo_description = fields.Html("Description", translate=True)
    woo_short_description = fields.Html("Short Description", translate=True)
    taxable = fields.Boolean("Taxable", default=True)
    woo_tmpl_id = fields.Char("Woo Template Id",size=100)
    exported_in_woo = fields.Boolean("Exported In Woo")
    website_published = fields.Boolean('Available in the website', copy=False)
    created_at = fields.Datetime("Created At")
    updated_at = fields.Datetime("Updated At")
    total_variants_in_woo = fields.Integer("Total Varaints in Woo", default=0,
                                           help="Total Variants in WooCommerce,"
                                                "\nDisplay after sync products")
    total_sync_variants = fields.Integer("Total Sync Variants",
                                         compute="_compute_total_sync_variants", store=True)
    woo_product_ids = fields.One2many("woo.product.product.ept", "woo_template_id", "Products")

    woo_categ_ids = fields.Many2many('woo.product.categ.ept', 'woo_template_categ_rel',
                                     'woo_template_id',
                                     'woo_categ_id', "Categories")
    woo_tag_ids = fields.Many2many('woo.tags.ept', 'woo_template_tags_rel', 'woo_template_id',
                                   'woo_tag_id', "Tags")
    woo_product_type = fields.Selection([('simple', 'Simple'),
                                         ('variable', 'Variable'),
                                         ('bundle','Bundle'),
                                         ('grouped','Grouped'),
                                         ('external','External')],
                                        string='Woo Product Type',)
    woo_image_ids = fields.One2many("woo.product.image.ept", "woo_template_id")


    @api.depends("woo_product_ids")
    def _compute_woo_product_type(self):
        """
        This method will set the product's type by counting the variants of a product.
        """
        for record in self:
            if len(record.woo_product_ids) > 1:
                record.woo_product_type = "variable"
            else:
                record.woo_product_type = "simple"

    @api.onchange("product_tmpl_id")
    def on_change_product(self):
        for record in self:
            record.name = record.product_tmpl_id.name

    def write(self, vals):
        """
        This method use to archive/unarchive woo product variants base on woo product templates.
        :parameter: self, vals
        :return: res
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 09/12/2019.
        :Task id: 158502
        """
        if 'active' in vals.keys():
            for woo_template in self:
                woo_template.woo_product_ids and woo_template.woo_product_ids.write(
                    {'active': vals.get('active')})
                if vals.get('active'):
                    woo_variants = self.env['woo.product.product.ept'].search(
                        [('woo_template_id', '=', woo_template.id), ('woo_instance_id', '=',
                                                                     woo_template.woo_instance_id.id),
                         ('active', '=', False)])
                    woo_variants and woo_variants.write({'active': vals.get('active')})
        res = super(WooProductTemplateEpt, self).write(vals)
        return res

    @api.model
    def get_variant_image(self, instance, variant):
        """
         This method is used for get the image of product and upload that image in woo commerce
        :param instance: It contain the browsable object of the current instance
        :param variant: It contain the woo product variant
        :return: return the image response in dictionary
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        variant_img_keys = {}
        key = False
        image_id = False
        variation_data = {}
        if instance.woo_is_image_url:
            if variant.response_url:
                try:
                    img = requests.get(variant.response_url, stream=True, verify=False, timeout=10)
                    if img.status_code == 200:
                        var_url = variant.response_url
                    elif variant.woo_variant_url or variant.product_id.image_url:
                        var_url = variant.woo_variant_url or variant.product_id.image_url or ''
                except Exception:
                    var_url = variant.woo_variant_url or variant.product_id.image_url or ''
            elif variant.woo_variant_url or variant.product_id.image_url:
                var_url = variant.woo_variant_url or variant.product_id.image_url or ''
        else:
            variant_images = variant.woo_image_ids
            if variant_images:
                if not variant_images[0].woo_image_id:
                    res = img_file_upload.upload_image(instance, variant_images[0].image,
                                                       "%s_%s" % (variant.name, variant.id))
                    image_id = res and res.get('id', False) or ''
                else:
                    image_id = variant_images[0].woo_image_id
        #         if var_url:
        #             if instance.woo_version == 'wc/v2' or instance.woo_version == 'wc/v3':
        #                 if instance.woo_is_image_url:
        #                     variation_data.update({"image": {'src': var_url, 'position': 0}})
        #                 else:
        #                     variation_data.update({"image": {'id': var_url, 'position': 0}})
        #             else:
        #                 if instance.woo_is_image_url:
        #                     variation_data.update({"image": [{'src': var_url, 'position': 0}]})
        #                 else:
        #                     variation_data.update({"image": [{'id': var_url, 'position': 0}]})
        if image_id:
            variation_data.update({"image": {'id': image_id}})
            variant_images[0].woo_image_id = image_id
        return variation_data

    @api.model
    def get_variant_data(self, variant, instance, update_image):
        """
        This method is used for prepare the product variant data with its image and return it into
        dictionary format
        :param variant: It contain the woo product variant
        :param instance: It contain the browsable object of the current instance
        :param update_image: It contain Either True or False
        :return: It will return the product variant details and its type is Dict.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        att = []
        woo_attribute_obj = self.env['woo.product.attribute.ept']
        variation_data = {}
        att_data = {}
        for attribute_value in variant.product_id.product_template_attribute_value_ids:
            if instance.woo_attribute_type == 'select':
                woo_attribute = woo_attribute_obj.search(
                    [('name', '=', attribute_value.attribute_id.name),
                     ('woo_instance_id', '=', instance.id),
                     ('exported_in_woo', '=', True)], limit=1)
                if not woo_attribute:
                    woo_attribute = woo_attribute_obj.search(
                        [('attribute_id', '=', attribute_value.attribute_id.id),
                         ('woo_instance_id', '=', instance.id),
                         ('exported_in_woo', '=', True)], limit=1)
                att_data = {
                    'id': woo_attribute and woo_attribute.woo_attribute_id,
                    'option': attribute_value.name
                }
            if instance.woo_attribute_type == 'text':
                att_data = {
                    'name': attribute_value.attribute_id.name,
                    'option': attribute_value.name
                }
            att.append(att_data)
        if update_image:
            variation_data.update(self.get_variant_image(instance, variant))

        weight = self.convert_weight_by_uom(variant.product_id.weight, instance)

        variation_data.update(
            {
                'attributes': att, 'sku': str(variant.default_code),
                'weight': str(weight), "manage_stock":variant.woo_is_manage_stock
            })
        return variation_data

    @api.model
    def get_product_price(self, instance, variant):
        """
        It will get the product price based on pricelist and return it
        :param instance: It contain the browsable object of the current instance
        :param variant: It contain the woo product variant
        :return: It will return the product regular price and sale price into Dict Format.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        price = instance.woo_pricelist_id.get_product_price_ept(variant.product_id)
        return {'regular_price': str(price), 'sale_price': str(price)}

    @api.model
    def get_product_stock(self, instance, variant):
        if variant.woo_is_manage_stock:
            quantity = self.get_stock(variant, instance.woo_warehouse_id.id,
                                      instance.woo_stock_field.name)
            return {'manage_stock': True, 'stock_quantity': int(quantity)}
        return {}

    @api.model
    def update_stock_old_api(self, instance=False, products=False):
        """
        This method is used for export stock from odoo to woo for WooCommerce older version (<3.0)
        :param instance: Instance Object
        :param products: Object of Woo Product Template
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd On Data 19-Nov-2019
        :Task id: 156886
        """
        common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "woo.product.product.ept"
        model_id = common_log_line_obj.get_model_id(model)
        log_line_id = []

        location_ids = instance.woo_warehouse_id.lot_stock_id.child_ids.ids
        location_ids.append(instance.woo_warehouse_id.lot_stock_id.id)
        woo_products = products
        if not woo_products:
            return False

        wcapi = instance.woo_connect()

        """
            woo_stock_key: used to manage keys according to WooCommerce version because there's changed
            Key of stock for different version API.
        """
        woo_stock_key = {}
        if instance.woo_version == 'v3':
            woo_stock_key.update({
                'is_manage': 'managing_stock',
                'api_url': 'products/bulk',
                'post_data_key': 'products'
            })
        else:
            woo_stock_key.update({
                'is_manage': 'manage_stock',
                'api_url': 'products/batch',
                'post_data_key': 'update',
            })
        batches = self.prepare_batches(woo_products)
        for woo_products in batches:
            batch_update = {'products': []}
            batch_update_data = []
            for template in woo_products:
                info = {'id': template.woo_tmpl_id, 'variations': []}
                flag = False
                for variant in template.woo_product_ids:
                    if variant.variant_id and variant.product_id.type == 'product' and variant.woo_is_manage_stock \
                            and variant.product_id.id in self._context.get(
                        'updated_products_in_inventory'):
                        quantity = self.get_stock(variant, instance.woo_warehouse_id.id,
                                                  instance.woo_stock_field.name)
                        if template.woo_tmpl_id != variant.variant_id:
                            info.get('variations').append(
                                {
                                    'id': variant.variant_id, woo_stock_key.get('is_manage'): True,
                                    'stock_quantity': int(quantity)
                                })
                            flag = True
                        elif template.woo_tmpl_id == variant.variant_id and variant.woo_is_manage_stock:
                            del info['variations']
                            info.update({
                                woo_stock_key.get('is_manage'): True,
                                'stock_quantity': int(quantity)
                            })
                            flag = True
                flag and batch_update_data.append(info)
            if batch_update:
                batch_update.update({woo_stock_key.get('post_data_key'): batch_update_data})
                _logger.info('Export Stock||Products batch processing')
                res = wcapi.post(woo_stock_key.get('api_url'), batch_update)
                _logger.info('Export Stock||Products batch completed [status: %s]', res.status_code)
                try:
                    response = res.json()
                except Exception as e:
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': "Json Error : While update product stock to WooCommerce for instance %s. \n%s" % (
                            instance.name, e),
                    })
                    log_line_id.append(log_id.id)
                errors = response.get('errors', '')
                if errors:
                    message = errors[0].get('message')
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': message
                    })
                    log_line_id.append(log_id.id)
        instance.write({'last_inventory_update_time': datetime.now()})
        if log_line_id:
            common_log_id = common_log_obj.create({
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance.id,
                'active': True,
            })
            common_log_line_obj.browse(log_line_id).write(
                {'log_line_id': common_log_id and common_log_id.id or False})
        return True

    def prepare_batches(self, data):
        """
        This method is used for create batches
        :param data:  It can be either object or list
        :return: list of batches
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd
        :Task id: 156886
        """
        batches = []
        start, end = 0, 100
        if len(data) > 100:
            while True:
                data_batch = data[start:end]
                if not data_batch:
                    break
                temp = end + 100
                start, end = end, temp
                if data_batch:
                    batches.append(data_batch)
        else:
            batches.append(data)
        return batches

    @api.model
    def update_stock_new_api(self, instance=False, products=False):
        """
        This method is used for export stock from odoo to woo for WooCommerce newer version (3.0+)
        :param instance: Instance Object
        :param products: Object of Woo Product Template
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd On Data 19-Nov-2019
        :Task id: 156886
        """
        common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "woo.product.product.ept"
        product_obj = self.env['product.product']
        model_id = common_log_line_obj.get_model_id(model)
        log_line_id = []
        location_ids = instance.woo_warehouse_id.lot_stock_id.child_ids.ids
        location_ids.append(instance.woo_warehouse_id.lot_stock_id.id)
        wcapi = instance.woo_connect()

        woo_products = products
        if not woo_products:
            return False
        # Update stock for variable type of product products
        product_ids = woo_products.mapped('woo_product_ids').mapped('product_id')
        export_product_stock = self.check_stock_type(instance,product_ids,product_obj,instance.woo_warehouse_id)
        for template in woo_products.filtered(lambda x: x.woo_product_type == 'variable'):
            info = {'id': template.woo_tmpl_id, 'variations': []}
            for variant in template.woo_product_ids:
                if variant.variant_id and variant.product_id.type == 'product' and variant.woo_is_manage_stock:
                    if variant.product_id.id in self._context.get('updated_products_in_inventory'):
                        quantity = [x['stock'] for i,x in enumerate(export_product_stock) if x['product_id']==variant.product_id.id][0]
                        if not quantity:
                            quantity = self.get_stock(variant, instance.woo_warehouse_id.id,
                                                      instance.woo_stock_field.name)
                        info.get('variations').append({
                            'id': variant.variant_id,
                            'manage_stock': True,
                            'stock_quantity': int(quantity)
                        })
            if instance.woo_version in ['wc/v2', 'wc/v3'] and info.get('variations'):
                variant_batches = self.prepare_batches(info.get('variations'))
                for woo_variants in variant_batches:
                    _logger.info('Export Stock||Variations batch processing')
                    res = wcapi.post('products/%s/variations/batch' % (info.get('id')),
                                     {'update': woo_variants})
                    _logger.info('Export Stock||Variations batch process completed [status: %s]',
                                 res.status_code)
                    if res.status_code not in [200, 201]:
                        log_id = common_log_line_obj.create({
                            'model_id': model_id,
                            'message': "Update Product Stock\n%s" % (res.content),
                        })
                        log_line_id.append(log_id.id)
        # Update stock for variable type of simple products
        woo_products_data = woo_products.filtered(lambda x: x.woo_product_type == 'simple')
        batches = self.prepare_batches(woo_products_data)
        for woo_products in batches:
            batch_update = {'update': []}
            batch_update_data = []
            for template in woo_products:
                info = {'id': template.woo_tmpl_id, 'variations': []}
                if template.woo_product_ids.woo_is_manage_stock:
                    quantity = [x['stock'] for i,x in enumerate(export_product_stock) if x['product_id']==template.woo_product_ids[0].product_id.id][0]
                    if not quantity:
                        quantity = self.get_stock(template.woo_product_ids,
                                                  instance.woo_warehouse_id.id,
                                                  instance.woo_stock_field.name)
                    info.update({'manage_stock': True, 'stock_quantity': int(quantity)})
                    batch_update_data.append(info)
            if batch_update_data:
                batch_update.update({'update': batch_update_data})
                _logger.info('products batch processing')
                res = wcapi.post('products/batch', batch_update)
                _logger.info('products batch completed [status: %s]', res.status_code)
                if not isinstance(res, requests.models.Response):
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': "Update Product Stock \nResponse is not in proper format :: %s" % (
                            res),
                    })
                    log_line_id.append(log_id.id)
                if res.status_code not in [200, 201]:
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': res.content,
                    })
                    log_line_id.append(log_id.id)
                try:
                    response = res.json()
                except Exception as e:
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': "Json Error : While update product stock to WooCommerce for instance %s. \n%s" % (
                            instance.name, e),
                    })
                    log_line_id.append(log_id.id)
                if response.get('data', {}) and response.get('data', {}).get('status') != 200:
                    message = response.get('message')
                    log_id = common_log_line_obj.create({
                        'model_id': model_id,
                        'message': message
                    })
                    log_line_id.append(log_id.id)
        instance.write({'last_inventory_update_time': datetime.now()})
        if log_line_id:
            common_log_id = common_log_obj.create({
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance.id,
                'active': True,
            })
            common_log_line_obj.browse(log_line_id).write(
                {'log_line_id': common_log_id and common_log_id.id or False})
        return True

    def check_stock_type(self, instance, product_ids, prod_obj, warehouse):
        """
        This Method relocates check type of stock.
        :param instance: This arguments relocates instance of Woocommerce.
        :param product_ids: This argumentes product listing id of odoo.
        :param prod_obj: This argument relocates product object of common connector.
        :param warehouse:This arguments relocates warehouse of Woocmmerce.
        :return: This Method return prouct listing stock.
        """
        prouct_listing_stock = False
        if product_ids:
            # prod_ids = prod_obj.browse(product_ids)
            if instance.woo_stock_field.name == 'qty_available':
                prouct_listing_stock = prod_obj.get_qty_on_hand(warehouse, product_ids)
            elif instance.woo_stock_field.name == 'virtual_available':
                prouct_listing_stock = prod_obj.get_forecated_qty(warehouse, product_ids)
        return prouct_listing_stock

    def get_stock(self, woo_product, warehouse_id, stock_type='virtual_available'):
        """
        This method is used to get stock.
        :param woo_product: woo product object
        :param warehouse_id: warehouse id which is associated to instance
        :param stock_type: stock type which is selected in instance configuration or else set type in woo product form.
        :return: stock value
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd
        :Task id: 156886
        """
        actual_stock = 0.0
        product = self.env['product.product'].with_context(warehouse=warehouse_id).browse(
            woo_product.product_id.id)
        if stock_type == 'virtual_available':
            if product.virtual_available > 0.0:
                actual_stock = product.virtual_available
        else:
            actual_stock = product.qty_available
        if actual_stock >= 1.00:
            if woo_product.fix_stock_type == 'fix':
                if woo_product.fix_stock_value >= actual_stock:
                    return actual_stock
                else:
                    return woo_product.fix_stock_value

            elif woo_product.fix_stock_type == 'percentage':
                quantity = int(actual_stock * woo_product.fix_stock_value) / 100
                if quantity >= actual_stock:
                    return actual_stock
                else:
                    return quantity
        return actual_stock

    def woo_unpublished(self):
        """
        This method is used for unpublish product from woo commerce store
        :param : self :- It is the browsable object of woo product template class
        :return: It will return True If product successfully unpublished from woo
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        instance = self.woo_instance_id
        woo_common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        woo_common_log_id = woo_common_log_obj.create(
            {
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance.id,
                'active': True,
            })
        wcapi = instance.woo_connect()
        if self.woo_tmpl_id:
            data = {'status': 'draft'}
            if instance.woo_version == 'v3':
                data = {'product': data}
            res = wcapi.put('products/%s' % (self.woo_tmpl_id), data)
            # res = wcapi.post('products/batch', {'update': [data]})
            if not isinstance(res, requests.models.Response):
                message = "Unpublish Product \nResponse is not in proper format :: %s" % (res)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id, False)
                return True
            if res.status_code not in [200, 201]:
                common_log_line_obj.woo_product_export_log_line(res.content, model_id,
                                                                woo_common_log_id, False)
                return True
            try:
                response = res.json()
            except Exception as e:
                message = "Json Error : While Unpublish Product with id %s from WooCommerce " \
                          "for instance %s. \n%s" % (self.woo_tmpl_id, instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id, False)
                return False
            if instance.woo_version == 'v3':
                errors = response.get('errors', '')
                if errors:
                    message = errors[0].get('message')
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    woo_common_log_id, False)

                else:
                    self.write({'website_published': False})
            else:
                if response.get('data', {}) and response.get('data', {}).get('status') not in [200,
                                                                                               201]:
                    message = response.get('message')
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    woo_common_log_id, False)

                else:
                    self.write({'website_published': False})
        return True

    def woo_published(self):
        """
        This method is used for publish product in woo commerce store
        :param : self :- It is the browsable object of woo product template class
        :return: It will return True If product successfully published in woo
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        instance = self.woo_instance_id
        woo_common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        woo_common_log_id = woo_common_log_obj.create(
            {
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance.id,
                'active': True,
            })
        wcapi = instance.woo_connect()
        if self.woo_tmpl_id:
            data = {'status': 'publish'}
            if instance.woo_version == 'v3':
                data = {'product': data}
            res = wcapi.put('products/%s' % (self.woo_tmpl_id), data)
            # res = wcapi.post('products/batch', {'update': [data]})
            if not isinstance(res, requests.models.Response):
                message = "Publish Product \nResponse is not in proper format :: %s" % (res)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id, False)
                return True
            if res.status_code not in [200, 201]:
                common_log_line_obj.woo_product_export_log_line(res.content, model_id,
                                                                woo_common_log_id, False)
                return True
            try:
                response = res.json()
            except Exception as e:
                message = "Json Error : While Publish Product with id %s from WooCommerce " \
                          "for instance %s. \n%s" % (self.woo_tmpl_id, instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id, False)
                return False
            if instance.woo_version == 'v3':
                errors = response.get('errors', '')
                if errors:
                    message = errors[0].get('message')
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    woo_common_log_id, False)
                else:
                    self.write({'website_published': True})
            else:
                if response.get('data', {}) and response.get('data', {}).get('status') not in [200,
                                                                                               201]:
                    message = response.get('message')
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    woo_common_log_id, False)
                else:
                    self.write({'website_published': True})
        return True

    def import_all_attribute_terms(self, wcapi, instance, woo_attribute_id, woo_common_log_id,
                                   model_id, page):
        """
        This method is used for get the attribute value response as per request by page wise and return it
        :param wcapi: It contain the connection object between odoo and woo
        :param instance: It contain the browsable object of the current instance
        :param woo_attribute_id: It contain the Woo product Attribute and its type is Object
        :param woo_common_log_id: It contain the common log book id and its type is Object
        :param model_id: It contain the id of the model class
        :param page: It contain the page number of woo commerce and its type if Integer
        :return: It will return response based on send request
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        if instance.woo_version == 'v3':
            res = wcapi.get("products/attributes/%s/terms?filter[limit]=1000&page=%s" % (
                woo_attribute_id.woo_attribute_id, page))
        else:
            res = wcapi.get("products/attributes/%s/terms" % (
                woo_attribute_id.woo_attribute_id), params={'per_page': 100, 'page': page})

        if not isinstance(res, requests.models.Response):
            message = "Get All Attribute Terms \nResponse is not in proper format :: %s" % (
                res)
            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                            woo_common_log_id,
                                                            False)
            return []
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id,
                                                            woo_common_log_id,
                                                            False)
            return []
        try:
            response = res.json()
        except Exception as e:
            message = "Json Error : While import product attribute terms from WooCommerce for " \
                      "instance %s. \n%s " % (instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                            woo_common_log_id,
                                                            False)
            return []
        if instance.woo_version == 'v3':
            errors = response.get('errors', '')
            if errors:
                message = errors[0].get('message')
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id,
                                                                False)
                return []
            return response.get('product_attribute_terms')
        else:
            return response

    def sync_woo_attribute_term(self, instance, woo_common_log_id):
        """
         This method is used for send the request in woo and get the response of product attribute Values
         and create that attribute Value into woo commerce connector of odoo
        :param instance: It contain the browsable object of the current instance
        :param woo_common_log_id: It contain the log book id and its type is object
        :return: It will return True if the process is successfully completed.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("woo.product.attribute.term.ept")
        obj_woo_attribute = self.env['woo.product.attribute.ept']
        obj_woo_attribute_term = self.env['woo.product.attribute.term.ept']
        odoo_attribute_value_obj = self.env['product.attribute.value']

        wcapi = instance.woo_connect()
        woo_attributes = obj_woo_attribute.search([('woo_instance_id', '=', instance.id)])
        attributes_term_data = []
        for woo_attribute in woo_attributes:
            if instance.woo_version == 'v3':
                response = wcapi.get("products/attributes/%s/terms?filter[limit]=1000" % (
                    woo_attribute.woo_attribute_id))
            else:
                response = wcapi.get(
                    "products/attributes/%s/terms" % (woo_attribute.woo_attribute_id),
                    params={'per_page': 100})
            try:
                attributes_term_data = response.json()
            except Exception as e:
                message = "Json Error : While import product attribute terms from WooCommerce " \
                          "for instance %s. \n%s " % (instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id,
                                                                False)
                return False
            if instance.woo_version == 'v3':
                attributes_term_data = attributes_term_data.get('product_attribute_terms')
            if not isinstance(attributes_term_data, list):
                message = "Response is not in proper format :: %s" % (attributes_term_data)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id,
                                                                False)
                continue
            total_pages = 1
            if instance.woo_version == 'v3':
                total_pages = response and response.headers.get('X-WC-TotalPages') or 1
            else:
                total_pages = response and response.headers.get('x-wp-totalpages') or 1
            if int(total_pages) >= 2:
                for page in range(2, int(total_pages) + 1):
                    attributes_term_data = attributes_term_data + self.import_all_attribute_terms(
                        wcapi, instance, woo_attribute, woo_common_log_id, model_id, page)
            if response.status_code in [201, 200]:
                for attribute_term in attributes_term_data:
                    woo_attribute_term = obj_woo_attribute_term.search(
                        [('woo_attribute_term_id', '=', attribute_term.get('id')),
                         ('woo_instance_id', '=', instance.id), ('exported_in_woo', '=', True)],
                        limit=1)
                    if woo_attribute_term:
                        continue
                    odoo_attribute_value = odoo_attribute_value_obj.search(
                        [('name', '=ilike', attribute_term.get('name')),
                         ('attribute_id', '=', woo_attribute.attribute_id.id)], limit=1)
                    if not odoo_attribute_value:
                        odoo_attribute_value = odoo_attribute_value.with_context(
                            active_id=False).create({
                            'name': attribute_term.get('name'),
                            'attribute_id': woo_attribute.attribute_id.id
                        })
                    woo_attribute_term = obj_woo_attribute_term.search(
                        [('attribute_value_id', '=', odoo_attribute_value.id),
                         ('attribute_id', '=', woo_attribute.attribute_id.id),
                         ('woo_attribute_id', '=', woo_attribute.id),
                         ('woo_instance_id', '=', instance.id),
                         ('exported_in_woo', '=', False)],
                        limit=1)
                    if woo_attribute_term:
                        woo_attribute_term.write({
                            'woo_attribute_term_id': attribute_term.get(
                                'id'),
                            'count': attribute_term.get('count'),
                            'slug': attribute_term.get('slug'),
                            'exported_in_woo': True
                        })
                    else:
                        obj_woo_attribute_term.create({
                            'name': attribute_term.get('name'),
                            'woo_attribute_term_id': attribute_term.get(
                                'id'),
                            'slug': attribute_term.get('slug'),
                            'woo_instance_id': instance.id,
                            'attribute_value_id': odoo_attribute_value.id,
                            'woo_attribute_id': woo_attribute.woo_attribute_id,
                            'attribute_id': woo_attribute.attribute_id.id,
                            'exported_in_woo': True,
                            'count': attribute_term.get('count')
                        })
            else:
                common_log_line_obj.woo_product_export_log_line(attribute_term.content, model_id,
                                                                woo_common_log_id,
                                                                False)
                continue
        return True

    def woo_import_all_attributes(self, wcapi, instance, woo_common_log_id, model_id, page):
        """
        This method is used for get the attribute response as per request by page wise and return it
        :param wcapi: It contain the connection object between odoo and woo
        :param instance: It contain the browsable object of the current instance
        :param woo_common_log_id: It contain the log book id and its type is object
        :param model_id: It contain the id of the model class
        :param page: It contain the page number of woo commerce and its type if Integer
        :return: It will return the response of product attribute into Dict Format.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        if instance.woo_version == 'v3':
            res = wcapi.get('products/attributes?filter[limit]=1000&page=%s' % (page))
        else:
            res = wcapi.get('products/attributes', params={'per_page': 100, 'page': page})

        if not isinstance(res, requests.models.Response):
            message = "Get All Attibutes \nResponse is not in proper format :: %s" % (res)
            common_log_line_obj.woo_product_export_log_line(message, model_id, woo_common_log_id,
                                                            False)
            return []
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id,
                                                            woo_common_log_id, False)
            return []
        try:
            response = res.json()
        except Exception as e:
            message = "Json Error : While import product attributes from WooCommerce for " \
                      "instance %s. \n%s " % (instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id, woo_common_log_id,
                                                            False)
            return []

        if instance.woo_version == 'v3':
            errors = response.get('errors', '')
            if errors:
                message = errors[0].get('message')
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                woo_common_log_id,
                                                                False)
                return []
            return response.get('product_attributes')
        else:
            return response

    def sync_woo_attribute(self, instance, woo_common_log_id):
        """
        This method is used for send the request in woo and get the response of product attribute
         and create that attribute into woo commerce connector of odoo
        :param instance: It contain the browsable object of the current instance
        :param woo_common_log_id: It contain the common log book id and its type is Object
        :return: It will return True if the process successfully completed.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id("woo.product.attribute.ept")
        obj_woo_attribute = self.env['woo.product.attribute.ept']
        odoo_attribute_obj = self.env['product.attribute']
        wcapi = instance.woo_connect()
        if instance.woo_version == 'v3':
            response = wcapi.get('products/attributes?filter[limit]=1000')
        else:
            response = wcapi.get("products/attributes", params={'per_page': 100})
        try:
            attributes_data = response.json()
        except Exception as e:
            message = "Json Error : While import product attributes from WooCommerce for " \
                      "instance %s. \n%s " % (instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id, woo_common_log_id,
                                                            False)
            return False
        if instance.woo_version == 'v3':
            attributes_data = response.get('product_attributes')
        if not isinstance(attributes_data, list):
            message = "Response is not in proper format :: %s" % (attributes_data)
            common_log_line_obj.woo_product_export_log_line(message, model_id, woo_common_log_id,
                                                            False)
            return True
        total_pages = 1
        if instance.woo_version == 'v3':
            total_pages = response and response.headers.get('X-WC-TotalPages') or 1
        else:
            total_pages = response and response.headers.get('x-wp-totalpages') or 1
        if int(total_pages) >= 2:
            for page in range(2, int(total_pages) + 1):
                attributes_data = attributes_data + self.woo_import_all_attributes(wcapi, instance,
                                                                                   woo_common_log_id,
                                                                                   model_id, page)
        if response.status_code in [201, 200]:
            for attribute in attributes_data:
                woo_attribute = obj_woo_attribute.search(
                    [('woo_attribute_id', '=', attribute.get('id')),
                     ('woo_instance_id', '=', instance.id), ('exported_in_woo', '=', True)],
                    limit=1)
                if woo_attribute:
                    continue
                odoo_attribute = odoo_attribute_obj.search(
                    [('name', '=ilike', attribute.get('name'))], limit=1)
                if not odoo_attribute:
                    odoo_attribute = odoo_attribute.create({'name': attribute.get('name')})
                woo_attribute = obj_woo_attribute.search([('attribute_id', '=', odoo_attribute.id),
                                                          ('woo_instance_id', '=', instance.id),
                                                          ('exported_in_woo', '=', False)], limit=1)
                if woo_attribute:
                    woo_attribute.write({
                        'woo_attribute_id': attribute.get('id'),
                        'order_by': attribute.get('order_by'),
                        'slug': attribute.get('slug'), 'exported_in_woo': True,
                        'has_archives': attribute.get('has_archives')
                    })
                else:
                    obj_woo_attribute.create(
                        {
                            'name': attribute.get('name'), 'woo_attribute_id': attribute.get('id'),
                            'order_by': attribute.get('order_by'),
                            'slug': attribute.get('slug'), 'woo_instance_id': instance.id,
                            'attribute_id': odoo_attribute.id,
                            'exported_in_woo': True, 'has_archives': attribute.get('has_archives')
                        })
        else:
            common_log_line_obj.create(
                {
                    'message': attributes_data.content,
                    'log_line_id': woo_common_log_id and woo_common_log_id.id or False,
                    'model_id': model_id,
                    'res_id': self and self.id or False
                })
            return True
        self.sync_woo_attribute_term(instance, woo_common_log_id)
        return True

    def import_all_woo_products(self, wcapi, instance, common_log_id, model_id, page):
        """
        :param wcapi: it contain the response of woo commerce product api and its type is object
        :param instance: It contain the browsable object of class woo_instance_ept
        :param comman_log_id: It contain the new log detail and its type is object
        :param model_id: It contain the id of the model
        :param page: It contain the products page number of woo commerce and its type is Integer
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        if instance.woo_version == 'v3':
            res = wcapi.get('products?page=%s' % (page))
        else:
            res = wcapi.get('products', params={'per_page': 100, 'page': page})
        if not isinstance(res, requests.models.Response):
            message = "Get All Products\nResponse is not in proper format :: %s" % (res)
            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                            common_log_id, False)
            return []
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id,
                                                            common_log_id, False)
            return []
        try:
            response = res.json()
        except Exception as e:
            message = "Json Error : While Import Product from WooCommerce for instance %s.\n%s" % (
                instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                            common_log_id, False)
            return []
        if instance.woo_version == 'v3':
            errors = response.get('errors', '')
            if errors:
                message = errors[0].get('message')
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id, False)
                return []
            return response.get('products')
        else:
            return response

    def import_all_draft_products(self, wcapi, instance, common_log_id, model_id, page):
        """
        :param wcapi: It contain the browsable object of woo commerce api
        :param instance: It contain the browsable object of class woo_instance_ept
        :param comman_log_id: It is the browsable object of common log book
        :param model_id: It contain the id of the Model and Its type is Integer
        :param page: It contain the products page number of woo commerce and its type is Integer
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        res = wcapi.get('products?filter[post_status]=draft&page=%s' % (page))
        if not isinstance(res, requests.models.Response):
            message = "Get All Draft Products\nResponse is not in proper format :: %s" % (res)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return []
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id, common_log_id,
                                                            False)
            return []
        try:
            response = res.json()
        except Exception as e:
            message = "Json Error : While Import Draft Products from WooCommerce for instance %s." \
                      " \n%s" % (instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return []
        return response.get('products')

    def get_products_from_woo_v3(self, instance, common_log_id, template_id=False):
        """
        :param instance: It contain the browsable object of class woo_instance_ept
        :param comman_log_id: It is the browsable object of common log book
        :param template_id: It contain the browsable object of class woo_product_template_ept
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        wcapi = instance.woo_connect()
        if template_id:
            res = wcapi.get('products/%s' % (template_id))
        else:
            res = wcapi.get('products?filter[limit]=6000')

        if not isinstance(res, requests.models.Response):
            message = "Get Products\nResponse is not in proper format :: %s" % (res)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return False
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id, common_log_id,
                                                            False)
            return False
        total_pages = res.headers.get('X-WC-TotalPages')
        try:
            res = res.json()
        except Exception as e:
            message = "Json Error : While Sync Products from WooCommerce for instance %s. \n%s" % (
                instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return False
        if not isinstance(res, dict):
            message = "Sync Products, Response is not in proper format"
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return True

        errors = res.get('errors', '')
        if errors:
            message = errors[0].get('message')
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return True

        if template_id:
            results = [res.get('product')]
        else:
            results = res.get('products')
            draft_res = wcapi.get('products?filter[post_status]=draft&filter[limit]=6000')
            if not isinstance(draft_res, requests.models.Response):
                message = "Get Draft Products\nResponse is not in proper format :: %s" % (
                    draft_res)
                common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id,
                                                                False)
            if draft_res.status_code not in [200, 201]:
                common_log_line_obj.woo_product_export_log_line(draft_res.content, model_id,
                                                                common_log_id, False)
            draft_total_pages = draft_res.headers.get('X-WC-TotalPages')
            try:
                draft_res = draft_res.json()
            except Exception as e:
                message = "Json Error : While Sync Draft Products from WooCommerce for instance " \
                          "%s. \n%s" % (instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id,
                                                                False)
                draft_res = []
            if not isinstance(draft_res, dict):
                message = "Sync Draft Products,Response is not in proper format"
                common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id,
                                                                False)
            results = results + draft_res.get('products')
            if draft_total_pages and int(draft_total_pages) >= 2:
                for page in range(2, int(draft_total_pages) + 1):
                    results = results + self.import_all_draft_products(wcapi, instance,
                                                                       common_log_id, model_id,
                                                                       page)
        if int(total_pages) >= 2:
            for page in range(2, int(total_pages) + 1):
                results = results + self.import_all_woo_products(wcapi, instance, common_log_id,
                                                                 model_id, page)

        return results

    def get_products_from_woo_v1_v2_v3(self, instance, common_log_id, template_id=False, import_all=False):
        """
        :param woo_instance: It contain the browsable object of class woo_instance_ept
        :param woo_comman_log_id: It is the browsable object of common log book
        :param woo_template_id: It contain the browsable object of class woo_product_template_ept
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        results = []
        wcapi = instance.woo_connect()
        if template_id:
            res = wcapi.get('products/%s' % (template_id))
        else:
            res = wcapi.get('products', params={'per_page': 100})
        if not isinstance(res, requests.models.Response):
            message = "Get Products\nResponse is not in proper format :: %s" % (res)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return False
        if res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(res.content, model_id, common_log_id,
                                                            False)
            return False
        total_pages = res.headers.get('x-wp-totalpages', 0)
        try:
            res = res.json()
        except Exception as e:
            message = "Json Error : While Import Product from WooCommerce for instance %s.\n%s" % (
                instance.name, e)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return []
        if template_id:
            results = [res]
        else:
            results = res
        if int(total_pages) >= 2:
            for page in range(2, int(total_pages) + 1):
                results += self.import_all_woo_products(wcapi, instance, common_log_id,
                                                        model_id, page)
        total_results = []
        if instance.woo_version == 'wc/v2' or instance.woo_version == 'wc/v3':
            available_queue = False
            product_data_queue_line_ids = False
            if not template_id and not import_all:
                product_data_queues = self.env['woo.product.data.queue.ept'].search(
                    [('woo_instance_id', '=', instance.id)])
                if product_data_queues:
                    available_queue = True
                    product_data_queue_line_ids = product_data_queues.queue_line_ids
            already_exist_result = False
            for result in results:
                flag = False
                variants = []
                woo_id = result.get('id')
                date_modified = result.get('date_modified', False)
                # Added the code to skip the product which is already create or available in queue
                if available_queue:
                    already_exist_results = product_data_queue_line_ids.filtered(
                        lambda x: int(x.woo_synced_data_id) == woo_id)
                    already_exist_results.sorted(lambda x: x.id, True)

                    for already_exist_result in already_exist_results:
                        if already_exist_result.state in ["draft", "done"]:
                            if already_exist_result.woo_update_product_date == date_modified:
                                flag = True
                                break
                            if already_exist_result.state == "draft":
                                break
                        already_exist_result = False
                        break
                if flag:
                    continue
                if result.get('variations'):
                    try:
                        params = {"per_page": 100}
                        response = wcapi.get("products/%s/variations" % (result.get("id")),
                                             params=params)
                        variants = response.json()

                        total_pages = response.headers.get("X-WP-TotalPages")
                        if int(total_pages) > 1:
                            for page in range(2, int(total_pages) + 1):
                                params["page"] = page
                                response = wcapi.get("products/%s/variations" % (result.get("id")), params=params)
                                variants += response.json()

                    except Exception as e:
                        message = "Json Error : While Import Product Variants from WooCommerce " \
                                  "for instance %s. \n%s" % (instance.name, e)
                        common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                        common_log_id, False)
                        continue
                result.update({'variations': variants})
                if already_exist_result:
                    already_exist_result.write({
                        'woo_synced_data': json.dumps(result),
                        'woo_update_product_date': date_modified
                    })
                else:
                    total_results.append(result)
        return total_results

    def search_odoo_product_variant(self, woo_instance, product_sku,
                                    variant_id):
        """
        :param woo_instance: It is the browsable object of woo commerce instance
        :param product_sku : It is the default code of product and its type is String
        :param variant_id : It is the id of the product variant and its type is Integer
        :return : It will returns the odoo product and woo product if it is exists
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        Modify by Haresh Mori on date 31/12/2019 modification adds active_test =False for searching an archived
        product for a webhook process.
        """
        odoo_product = self.env['product.product']
        woo_product_obj = self.env['woo.product.product.ept']

        woo_product = woo_product_obj.with_context(active_test=False).search(
            [('variant_id', '=', variant_id), ('woo_instance_id', '=', woo_instance.id)],
            limit=1)
        if not woo_product:
            woo_product = woo_product_obj.with_context(active_test=False).search(
                [('default_code', '=', product_sku), ('woo_instance_id', '=', woo_instance.id)],
                limit=1)
        if not woo_product:
            woo_product = woo_product_obj.with_context(active_test=False).search([(
                'product_id.default_code', '=', product_sku),
                ('woo_instance_id', '=', woo_instance.id)],
                limit=1)
        if not woo_product:
            odoo_product = odoo_product.search([('default_code', '=', product_sku)],
                                               limit=1)
        return woo_product, odoo_product

    def woo_create_variant_product(self, product_template_dict, woo_instance):
        """
        :param product_template_dict: It contain the product template info with variants and its
                                    type is Dictionary
        :param woo_instance: It is the browsable object of woo commerce instance
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        product_template_obj = self.env['product.template']

        template_title = ''
        if product_template_dict.get('name', ''):
            template_title = product_template_dict.get('name')
        if product_template_dict.get('title', ''):
            template_title = product_template_dict.get('title')
        attrib_line_vals = []

        for attrib in product_template_dict.get('attributes'):
            if not attrib.get('variation'):
                continue
            attrib_name = attrib.get('name')
            attrib_values = attrib.get('options')
            attribute = product_attribute_obj.get_attribute(attrib_name, type='radio',
                                                            create_variant='always',
                                                            auto_create=True)
            attribute = attribute.filtered(lambda x: x.name == attrib_name)[0] if len(
                attribute) > 1 else attribute
            attr_val_ids = []

            for attrib_vals in attrib_values:
                attrib_value = product_attribute_value_obj.get_attribute_values(attrib_vals,
                                                                                attribute.id,
                                                                                auto_create=True)
                attrib_value = attrib_value.filtered(lambda x: x.name == attrib_vals)[0] if len(
                    attrib_value) > 1 else attrib_value
                attr_val_ids.append(attrib_value.id)

            if attr_val_ids:
                attribute_line_ids_data = [0, False, {
                    'attribute_id': attribute.id,
                    'value_ids': [[6, False, attr_val_ids]]
                }]
                attrib_line_vals.append(attribute_line_ids_data)
        if attrib_line_vals:
            product_template_values = {
                'name': template_title,
                'type': 'product',
                'attribute_line_ids': attrib_line_vals,
            }
            if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                product_template_values.update({"description_sale": product_template_dict.get("description", "")})
            product_template = product_template_obj.create(product_template_values)

            available_odoo_products = self.woo_set_variant_sku(woo_instance, product_template_dict,
                                                               product_template,
                                                               sync_price_with_product=woo_instance.sync_price_with_product)
            if available_odoo_products:
                return product_template, available_odoo_products
            return False, False

    @api.model
    def find_template_attribute_values(self, template_attributes, variation_attributes,
                                       product_template, woo_instance):
        """
        Finds template's attribute values combination records and prepare domain for searching the odoo product.
        @author: Maulik Barad on Date 06-Dec-2019.
        @param template_attributes: Attributes of Woo template.
        @param variation_attributes: Attributes of Woo product.
        @param product_template: Odoo template.
        @param woo_instance: Instance of Woo.
        """
        template_attribute_value_domain = []
        for variation_attribute in variation_attributes:
            attribute_val = variation_attribute.get('option')
            attribute_name = variation_attribute.get('name')
            for attribute in template_attributes:
                if attribute.get('variation') and attribute.get('name'):
                    if attribute.get('name').replace(" ", "-").lower() == attribute_name:
                        attribute_name = attribute.get('name')
                        break
            product_attributes = self.env["product.attribute"].get_attribute(attribute_name,
                                                                            type="radio",
                                                                            create_variant="always",
                                                                            auto_create=True)
            for product_attribute in product_attributes:
                product_attribute_value = self.env[
                    "product.attribute.value"].get_attribute_values(attribute_val,
                                                                    product_attribute.id,
                                                                    auto_create=True)
                if product_attribute_value:
                    template_attribute_value_id = self.env[
                        'product.template.attribute.value'].search(
                        [('product_attribute_value_id', '=', product_attribute_value.id),
                         ('attribute_id', '=', product_attribute.id),
                         ('product_tmpl_id', '=', product_template.id)], limit=1)
                    if template_attribute_value_id:
                        domain = ('product_template_attribute_value_ids', '=',
                                  template_attribute_value_id.id)
                        template_attribute_value_domain.append(domain)
        return template_attribute_value_domain

    def woo_set_variant_sku(self, woo_instance, product_template_dict,
                            product_template, sync_price_with_product=False):
        """
        :param woo_instance: It contain the browsable object of the current instance
        :param product_template_dict: It contain the product template info with variants and
                                    type is Dictionary
        :param product_template: It is the browsable object of product template
        :param sync_price_with_product: It contain the value od price if it is sync or not with
                                        product and Its type is Boolean
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        odoo_product_obj = self.env['product.product']
        available_odoo_products = {}
        for variation in product_template_dict.get('variations'):
            odoo_product = False

            sku = variation.get('sku')
            price = variation.get('regular_price') or variation.get('sale_price') or 0.0
            woo_weight = float(variation.get("weight") or "0.0")
            variation_attributes = variation.get('attributes')

            if len(product_template.attribute_line_ids.ids) != len(variation_attributes):
                continue

            template_attribute_value_domain = self.find_template_attribute_values(
                product_template_dict.get("attributes"), variation_attributes, product_template,
                woo_instance)

            if template_attribute_value_domain:
                template_attribute_value_domain.append(
                    ('product_tmpl_id', '=', product_template.id))
                odoo_product = odoo_product_obj.search(template_attribute_value_domain)
                if odoo_product:
                    weight = self.convert_weight_by_uom(woo_weight, woo_instance, import_process=True)
                    odoo_product.write({'default_code': sku, "weight":weight})
                    available_odoo_products.update({variation["id"]: odoo_product})
                    if sync_price_with_product:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                             ('product_id', '=', odoo_product.id)], limit=1)
                        if not pricelist_item:
                            woo_instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': odoo_product.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if product_template.company_id and pricelist_item.currency_id.id != \
                                    product_template.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = product_template.company_id.currency_id
                                #                                 date = self._context.get('date') or
                                #                                 fields.Date.today()
                                #                                 company = product_template.company_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            #                                 price = instance_currency._convert(float(price),
                            #                                 product_company_currency, company, date)
                            pricelist_item.write({'fixed_price': price})
        if not available_odoo_products:
            product_template.sudo().unlink()
        return available_odoo_products

    def sync_woo_categ_with_product_v1_v2_v3(self, instance, woo_common_log_id, woo_categories,
                                             sync_images_with_product=True):
        """
        :param instance: It is the browsable object of the woo commerce instance
        :param woo_common_log_id: It contain the log id of the common log book and its type is object
        :param woo_categories: It contain the category details of products and and its type is Dict
        :param sync_images_with_product: It contain the either True or False and its type is Boolean
        :return: It will return the category ids into list format
        """
        obj_woo_product_categ = self.env['woo.product.categ.ept']
        categ_ids = []
        for woo_category in woo_categories:
            woo_product_categ = obj_woo_product_categ.search(
                [('woo_categ_id', '=', woo_category.get('id')),
                 ('woo_instance_id', '=', instance.id)], limit=1)
            if not woo_product_categ:
                woo_product_categ = obj_woo_product_categ.search(
                    [('slug', '=', woo_category.get('slug')),
                     ('woo_instance_id', '=', instance.id)], limit=1)
            if woo_product_categ:
                woo_product_categ.write(
                    {
                        'woo_categ_id': woo_category.get('id'), 'name': woo_category.get('name'),
                        'display': woo_category.get('display'), 'slug': woo_category.get('slug'),
                        'exported_in_woo': True
                    })
                obj_woo_product_categ.sync_woo_product_category(instance, woo_common_log_id,
                                                                woo_product_categ=woo_product_categ,
                                                                sync_images_with_product=sync_images_with_product)
                categ_ids.append(woo_product_categ.id)
            else:
                woo_product_categ = obj_woo_product_categ.create(
                    {
                        'woo_categ_id': woo_category.get('id'), 'name': woo_category.get('name'),
                        'display': woo_category.get('display'), 'slug': woo_category.get('slug'),
                        'woo_instance_id': instance.id, 'exported_in_woo': True
                    })
                obj_woo_product_categ.sync_woo_product_category(instance, woo_common_log_id,
                                                                woo_product_categ=woo_product_categ,
                                                                sync_images_with_product=sync_images_with_product)
                woo_product_categ and categ_ids.append(woo_product_categ.id)
        return categ_ids

    def sync_woo_tags_with_product_v1_v2_v3(self, woo_instance, woo_tags):
        """
        :param woo_instance: It is the browsable object of the woo commerce instance
        :param woo_tags: It contain the tags details of products and and its type is Dict
        :param woo_log_id: It contain the log id of the common log book and its type is object
        :return: It will return the tags ids into list format
        """
        woo_product_tags_obj = self.env['woo.tags.ept']
        tag_ids = []
        for woo_tag in woo_tags:
            woo_product_tag = woo_product_tags_obj.search(
                [('woo_tag_id', '=', woo_tag.get('id')),
                 ('woo_instance_id', '=', woo_instance.id)],
                limit=1)
            if not woo_product_tag:
                woo_product_tag = woo_product_tags_obj.search(
                    [('slug', '=', woo_tag.get('slug')),
                     ('woo_instance_id', '=', woo_instance.id)],
                    limit=1)
            if woo_product_tag:
                woo_product_tag.write({
                    'name': woo_tag.get('name'), 'slug': woo_tag.get('slug'),
                    'exported_in_woo': True
                })
                tag_ids.append(woo_product_tag.id)
            else:
                woo_product_tag = woo_product_tags_obj.create(
                    {
                        'woo_tag_id': woo_tag.get('id'), 'name': woo_tag.get('name'),
                        'slug': woo_tag.get('slug'), 'woo_instance_id': woo_instance.id,
                        'exported_in_woo': True
                    })
                woo_product_tag and tag_ids.append(woo_product_tag.id)
        return tag_ids

    def is_product_importable(self, result, instance, odoo_product, woo_product):
        """
        :param result: It contain the products detail and its type is Dictionary
        :param instance: It is the browsable object of woo commerce instance
        :param odoo_product: It contain the product variant of odoo and its type is object
        :param woo_product: It contain the woo product variant and its type is object
        :return: It will return the message if error is occur
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        woo_skus = []
        odoo_skus = []
        variations = result.get('variations')

        # if instance.woo_version == "new" or instance.woo_version == 'new+':
        if instance.woo_version != 'v3':
            template_title = result.get('name')
        else:
            template_title = result.get('title')

        product_count = len(variations)

        importable = True
        message = ""

        if not odoo_product and not woo_product:
            if product_count != 0:
                attributes = 1
                for attribute in result.get('attributes'):
                    if attribute.get('variation'):
                        attributes *= len(attribute.get('options'))

            product_attributes = {}
            for variantion in variations:
                sku = variantion.get("sku")
                attributes = variantion.get('attributes')
                attributes and product_attributes.update({sku: attributes})
                sku and woo_skus.append(sku)
            if not product_attributes and result.get('type') == 'variable':
                message = "Attributes are not set in any variation of Product: %s and ID: %s." % (
                    template_title, result.get("id"))
                importable = False
                return importable, message
            if woo_skus:
                woo_skus = list(filter(lambda x: len(x) > 0, woo_skus))
            total_woo_sku = len(set(woo_skus))
            if not len(woo_skus) == total_woo_sku:
                duplicate_skus = list(
                    set([woo_sku for woo_sku in woo_skus if woo_skus.count(woo_sku) > 1]))
                message = "Duplicate SKU(%s) found in Product: %s and ID: %s." % (duplicate_skus,
                                                                                  template_title,
                                                                                  result.get("id"))
                importable = False
                return importable, message
        woo_skus = []
        if odoo_product:
            odoo_template = odoo_product.product_tmpl_id
            if not (product_count == 0 and odoo_template.product_variant_count == 1):
                if product_count == odoo_template.product_variant_count:
                    for woo_sku, odoo_sku in zip(result.get('variations'),
                                                 odoo_template.product_variant_ids):
                        woo_skus.append(woo_sku.get('sku'))
                        odoo_sku.default_code and odoo_skus.append(odoo_sku.default_code)

                    woo_skus = list(filter(lambda x: len(x) > 0, woo_skus))
                    odoo_skus = list(filter(lambda x: len(x) > 0, odoo_skus))

                    total_woo_sku = len(set(woo_skus))
                    if not len(woo_skus) == total_woo_sku:
                        duplicate_skus = list(
                            set([woo_sku for woo_sku in woo_skus if woo_skus.count(woo_sku) > 1]))
                        message = "Duplicate SKU(%s) found in Product: %s and ID: %s." % (
                            duplicate_skus,
                            template_title, result.get("id"))
                        importable = False
                        return importable, message

        if woo_product:
            woo_skus = []
            for woo_sku in result.get('variations'):
                woo_skus.append(woo_sku.get('sku'))

            total_woo_sku = len(set(woo_skus))
            if not len(woo_skus) == total_woo_sku:
                duplicate_skus = list(
                    set([woo_sku for woo_sku in woo_skus if woo_skus.count(woo_sku) > 1]))
                message = "Duplicate SKU(%s) found in Product: %s and ID: %s." % (duplicate_skus,
                                                                                  template_title,
                                                                                  result.get("id"))
                importable = False
                return importable, message

        return importable, message

    def woo_sync_categ_with_product_v3(self, instance, common_log_id, woo_categories,
                                       sync_images_with_product=True):
        woo_product_categ = self.env['woo.product.categ.ept']
        categ_ids = []
        for woo_category in woo_categories:
            ctg = woo_category.lower().replace('\'', '\'\'')
            self._cr.execute(
                "select id from woo_product_categ_ept where LOWER(name) = '%s' and woo_instance_id = %s limit 1" % (
                    ctg, instance.id))
            woo_product_categ_id = self._cr.dictfetchall()
            woo_categ = False
            if woo_product_categ_id:
                woo_categ = woo_product_categ.browse(woo_product_categ_id[0].get('id'))
                categ_ids.append(woo_categ.id)
                woo_categ = woo_product_categ.sync_woo_product_category(instance, common_log_id,
                                                                        woo_product_categ=woo_categ,
                                                                        sync_images_with_product=sync_images_with_product)
            else:
                woo_categ = woo_product_categ.sync_woo_product_category(instance, common_log_id,
                                                                        woo_product_categ_name=woo_category,
                                                                        sync_images_with_product=sync_images_with_product)
                woo_categ and categ_ids.append(woo_categ.id)
        return categ_ids

    def woo_sync_tags_with_product_v3(self, wcapi, instance, common_log_id, model_id, woo_tags):
        common_log_line_obj = self.env['common.log.lines.ept']
        woo_product_tags = self.env['woo.tags.ept']
        tag_ids = []
        for woo_tag in woo_tags:
            tag = woo_tag.lower().replace('\'', '\'\'')
            self._cr.execute(
                "select id from woo_tags_ept where LOWER(name) = '%s' and woo_instance_id = %s limit 1" % (
                    tag, instance.id))
            woo_product_tag_id = self._cr.dictfetchall()
            woo_product_tag = False
            if woo_product_tag_id:
                woo_product_tag = woo_product_tags.browse(woo_product_tag_id[0].get('id'))
                tag_ids.append(woo_product_tag.id)
            else:
                tag_res = wcapi.get("products/tags?fields=id,name")
                if not isinstance(tag_res, requests.models.Response):
                    message = "Get Product Tags\nResponse is not in proper format :: %s" % (tag_res)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id, False)
                    continue
                if tag_res.status_code not in [200, 201]:
                    common_log_line_obj.woo_product_export_log_line(tag_res.content, model_id,
                                                                    common_log_id, False)
                    continue
                try:
                    tag_response = tag_res.json()
                except Exception as e:
                    message = "Json Error : While Sync Product Tags from WooCommerce for instance" \
                              " %s. \n%s" % (instance.name, e)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id, False)
                    continue
                product_tags = tag_response.get('product_tags')
                if isinstance(product_tags, dict):
                    product_tags = [product_tags]
                for product_tag in product_tags:
                    tag_name = product_tag.get('name')
                    if tag_name == woo_tag:
                        single_tag_res = wcapi.get("products/tags/%s" % (product_tag.get('id')))
                        if not isinstance(single_tag_res, requests.models.Response):
                            message = "Get Product Tags\nResponse is not in proper format :: %s" % (
                                single_tag_res)
                            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                            common_log_id, False)
                            continue
                        try:
                            single_tag_response = single_tag_res.json()
                        except Exception as e:
                            message = "Json Error : While Sync Product Tag with id %s from " \
                                      "WooCommerce for instance %s. \n%s" % (
                                          woo_tag.woo_tag_id, instance.name, e)
                            common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                            common_log_id, False)
                            continue
                        single_tag = single_tag_response.get('product_tag')

                        tag_vals = {
                            'name': woo_tag, 'woo_instance_id': instance.id,
                            'description': single_tag.get('description'),
                            'exported_in_woo': True, 'woo_tag_id': single_tag.get('id')
                        }

                        woo_product_tag = woo_product_tags.create(tag_vals)
                        woo_product_tag and tag_ids.append(woo_product_tag.id)
                        break
        return tag_ids

    def woo_sync_products_v3(self, product_data_queue, instance, import_for_order=False,
                             update_price=False, sync_images_with_product=False,
                             skip_existing_products=False, update_templates=True):
        woo_common_log_obj = self.env["common.log.book.ept"]
        process_import_export_obj = self.env['woo.process.import.export']
        if instance.woo_attribute_type == 'select' and not import_for_order:
            process_import_export_obj.sync_woo_attributes(instance)
        woo_product_obj = self.env['woo.product.product.ept']
        common_log_line_obj = self.env["common.log.lines.ept"]
        common_product_image_obj = self.env["common.product.image.ept"]
        product_template_obj = self.env['product.template']
        product_variant_obj = self.env['product.product']
        model_id = common_log_line_obj.get_model_id("woo.product.template.ept")
        wcapi = instance.woo_connect()
        product_queue_dict = {}
        common_log_id = woo_common_log_obj.create(
            {
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance.id,
                'active': True,
            })
        if not import_for_order:
            product_queue_id = product_data_queue[0].queue_id.id
            _logger.info('Product Sync Process Start of Product Queue {}'.format(product_queue_id))
        result = False
        for queue_line_id in product_data_queue:
            if not import_for_order:
                _logger.info(
                    'Process Start of Product Queue Line {0} of Product Queue {1}'.format(
                        queue_line_id.id, product_queue_id))
                result = json.loads(queue_line_id.woo_synced_data)
            else:
                result = queue_line_id

            woo_product = website_published = odoo_product = updated_template = onetime_call = is_importable = False
            odoo_product_images = []
            woo_tmpl_id = result.get('id')
            woo_template = self.search(
                [('woo_tmpl_id', '=', woo_tmpl_id), ('woo_instance_id', '=', instance.id)],
                limit=1)
            if woo_template and not update_templates:
                continue

            template_title = result.get('title')
            template_created_at = result.get('created_at')
            template_updated_at = result.get('updated_at')
            price = result.get('regular_price') or result.get('sale_price')

            if template_created_at.startswith('-'):
                template_created_at = template_created_at[1:]
            if template_updated_at.startswith('-'):
                template_updated_at = template_updated_at[1:]

            template_created_at = datetime.strptime(template_created_at,
                                                    "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%d %H:%M:%S") if template_created_at else ''
            template_updated_at = datetime.strptime(template_updated_at,
                                                    "%Y-%m-%dT%H:%M:%SZ").strftime(
                "%Y-%m-%d %H:%M:%S") if template_updated_at else ''

            short_description = result.get('short_description')
            description = result.get('description')
            status = result.get('status')
            taxable = result.get('taxable')

            if status == 'publish':
                website_published = True

            tmpl_info = {
                'name': template_title, 'created_at': template_created_at or False,
                'updated_at': template_updated_at or False,
                'woo_short_description': short_description, 'woo_description': description,
                'website_published': website_published, 'taxable': taxable
            }

            for variation in result.get('variations'):
                variant_id = variation.get('id')
                sku = variation.get('sku')
                price = result.get('regular_price') or result.get('sale_price')
                woo_is_manage_stock = True if variation.get('managing_stock') else False
                woo_product, odoo_product = self.search_odoo_product_variant(instance, sku,
                                                                             variant_id)
                if woo_product and skip_existing_products:
                    # Added code for skip the product sync if already product imported
                    continue

                # Added this in the case of odoo product is not found
                if woo_product and not odoo_product:
                    odoo_product = woo_product.product_id

                is_importable = True
                message = ""

                is_importable, message = self.is_product_importable(result, instance, odoo_product,
                                                                    woo_product)
                if not is_importable:
                    log_id = common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                             queue_line_id)
                    if not import_for_order:
                        _logger.info(
                            'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                            'Reason is {2}'.format(queue_line_id.id, product_queue_id, message))
                    if log_id:
                        queue_line_id.write({'state': "failed"})
                    break

                if not odoo_product and not woo_product:
                    if instance.auto_import_product:
                        if not onetime_call:
                            self.woo_create_variant_product(result, instance)
                            odoo_product = product_variant_obj.search([('default_code', '=', sku)],
                                                                      limit=1)
                            onetime_call = True
                            if not odoo_product:
                                message = "Attribute(s) are not set properly in Product: %s and ID: %s." % (
                                    template_title, result.get('id'))
                                log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                         model_id,
                                                                                         queue_line_id)
                                if not import_for_order:
                                    _logger.info(
                                        'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                        'Reason is {2}'.format(queue_line_id.id,
                                                               product_queue_id,
                                                               message))
                                if log_id:
                                    queue_line_id.write({'state': "failed"})
                                break
                    else:
                        message = "%s Product Not found for sku %s" % (template_title, sku)
                        log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                 model_id,
                                                                                 queue_line_id)
                        if not import_for_order:
                            _logger.info(
                                'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                'Reason is {2}'.format(queue_line_id.id, product_queue_id,
                                                       message))
                        if log_id:
                            queue_line_id.write({'state': "failed"})
                        continue

                variant_info = {}
                var_img = False
                price = variation.get('regular_price') or variation.get('sale_price')
                if sync_images_with_product:
                    var_images = variation.get('image')
                    var_image_src = ''
                    var_image_id = False
                    for var_image in var_images:
                        if str(var_image.get('title').encode(
                                'utf-8')) == 'Placeholder' or not var_image.get('id'):
                            continue
                        if var_image.get('position') == 0:
                            var_image_src = var_image.get('src')
                            var_image_id = var_image.get('id')
                            if not instance.woo_is_image_url and var_image_src:
                                try:
                                    res_img = requests.get(var_image_src, stream=True, verify=False,
                                                           timeout=10)
                                    if res_img.status_code == 200:
                                        var_img = base64.b64encode(res_img.content)
                                except Exception:
                                    pass

                created_at = variation.get('created_at')
                updated_at = variation.get('updated_at')
                if created_at.startswith('-'):
                    created_at = created_at[1:]
                if updated_at.startswith('-'):
                    updated_at = updated_at[1:]

                created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                    "%Y-%m-%d %H:%M:%S") if created_at else ''
                updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                    "%Y-%m-%d %H:%M:%S") if updated_at else ''

                variant_info = {
                    'name': template_title, 'default_code': sku,
                    'created_at': created_at, 'updated_at': updated_at
                }
                if instance.woo_is_image_url and sync_images_with_product:
                    variant_info.update(
                        {'response_url': var_image_src, 'woo_image_id': var_image_id})

                if not woo_product:
                    if not woo_template:
                        woo_categories = result.get('categories')
                        categ_ids = self.woo_sync_categ_with_product_v3(instance, common_log_id,
                                                                        woo_categories,
                                                                        sync_images_with_product)

                        woo_tags = result.get('tags')
                        tag_ids = self.woo_sync_tags_with_product_v3(wcapi, instance, common_log_id,
                                                                     model_id,
                                                                     woo_tags)
                        tmpl_info.update({
                            'product_tmpl_id': odoo_product.product_tmpl_id.id,
                            'woo_instance_id': instance.id,
                            'woo_tmpl_id': woo_tmpl_id, 'taxable': taxable,
                            'exported_in_woo': True,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'woo_product_type': result.get('type', ''),
                            'total_variants_in_woo': len(result.get('variations'))
                        })

                        woo_template = self.create(tmpl_info)
                    variant_info.update({
                        'product_id': odoo_product.id,
                        'name': template_title,
                        'variant_id': variant_id,
                        'woo_template_id': woo_template.id,
                        'woo_instance_id': instance.id,
                        'exported_in_woo': True,
                        'woo_is_manage_stock': woo_is_manage_stock,
                    })
                    woo_product = woo_product_obj.create(variant_info)
                    if not instance.woo_is_image_url:
                        odoo_product_images.append({
                            'odoo_product': odoo_product,
                            'image': var_img if woo_product else None,
                            'sku': sku, 'image_id': var_image_id
                        })
                        # odoo_product.image_1920 = var_img if woo_product else None
                    if update_price:
                        woo_product.product_id.write({'list_price': price.replace(",", ".")})
                else:
                    if not updated_template:
                        woo_categories = result.get('categories')
                        categ_ids = self.woo_sync_categ_with_product_v3(instance, common_log_id,
                                                                        woo_categories,
                                                                        sync_images_with_product)

                        woo_tags = result.get('tags')
                        tag_ids = self.woo_sync_tags_with_product_v3(wcapi, instance, common_log_id,
                                                                     model_id,
                                                                     woo_tags)
                        tmpl_info.update({
                            'woo_tmpl_id': woo_tmpl_id, 'taxable': taxable,
                            'exported_in_woo': True,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'woo_product_type': result.get('type', ''),
                            'total_variants_in_woo': len(result.get('variations'))
                        })
                        updated_template = True
                        if not woo_template:
                            woo_template = woo_product.woo_template_id

                        woo_template.write(tmpl_info)
                    variant_info.update({
                        'variant_id': variant_id,
                        'woo_template_id': woo_template.id,
                        'woo_instance_id': instance.id,
                        'exported_in_woo': True,
                        'woo_is_manage_stock': woo_is_manage_stock,
                    })
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', instance.woo_pricelist_id.id),
                             ('product_id', '=', odoo_product.id)], limit=1)
                        if not pricelist_item:
                            instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': odoo_product.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
                    woo_product.write(variant_info)
                    if not instance.woo_is_image_url and sync_images_with_product:
                        odoo_product_images.append({
                            'odoo_product': odoo_product,
                            'image': var_img if woo_product else None,
                            'sku': sku, 'image_id': var_image_id
                        })
                        # woo_product.product_id.image_1920 = var_img if woo_product else None
            if not result.get('variations'):
                woo_is_manage_stock = True if result.get('managing_stock') else False
                sku = result.get('sku')
                price = result.get('regular_price') or result.get('sale_price')
                woo_product, odoo_product = self.search_odoo_product_variant(instance, sku,
                                                                             woo_tmpl_id)

                # Added in the case of odoo product not found but woo product is found
                if woo_product and not odoo_product:
                    odoo_product = woo_product.product_id
                is_importable = True
                is_importable, message = self.is_product_importable(result, instance, odoo_product,
                                                                    woo_product)
                if not is_importable:
                    log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                             model_id,
                                                                             queue_line_id)
                    if not import_for_order:
                        _logger.info(
                            'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                            'Reason is {2}'.format(queue_line_id.id, product_queue_id, message))
                    if log_id:
                        queue_line_id.write({'state': "failed"})
                    continue

                if not odoo_product and not woo_product:
                    if sku:
                        if not result.get('parent_id'):
                            if instance.auto_import_product:
                                vals = {
                                    'name': template_title,
                                    'default_code': sku,
                                    'type': 'product',
                                }
                                product_template = product_template_obj.create(vals)
                                odoo_product = product_template.product_variant_ids
                                if update_price:
                                    pricelist_item = self.env['product.pricelist.item'].search(
                                        [('pricelist_id', '=', instance.woo_pricelist_id.id),
                                         ('product_id', '=', odoo_product.id)], limit=1)
                                    if not pricelist_item:
                                        instance.woo_pricelist_id.write({
                                            'item_ids': [(0, 0, {
                                                'applied_on': '0_product_variant',
                                                'product_id': odoo_product.id,
                                                'compute_price': 'fixed',
                                                'fixed_price': price
                                            })]
                                        })
                                    else:
                                        if pricelist_item.currency_id.id != product_template.company_id.currency_id.id:
                                            instance_currency = pricelist_item.currency_id
                                            product_company_currency = product_template.company_id.currency_id
                                            price = instance_currency.compute(float(price),
                                                                              product_company_currency)
                                    pricelist_item.write({'fixed_price': price})
                            else:
                                message = "%s Product Not found for sku %s" % (template_title, sku)
                                log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                         model_id,
                                                                                         queue_line_id)
                                if not import_for_order:
                                    _logger.info(
                                        'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                        'Reason is {2}'.format(queue_line_id.id,
                                                               product_queue_id,
                                                               message))
                                if log_id:
                                    queue_line_id.write({'state': "failed"})
                                continue
                        else:
                            message = "%s Product and id %s and sku %s is a variant product it cannot import." % (
                                template_title, result.get('id'), sku)
                            log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                     model_id,
                                                                                     queue_line_id)
                            if not import_for_order:
                                _logger.info(
                                    'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                    'Reason is {2}'.format(queue_line_id.id, product_queue_id,
                                                           message))
                            if log_id:
                                queue_line_id.write({'state': "failed"})
                            continue
                    else:
                        message = "SKU not set in Product: %s and ID: %s." % (
                            template_title, result.get('id'))
                        log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                 model_id,
                                                                                 queue_line_id)
                        if not import_for_order:
                            _logger.info(
                                'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                'Reason is {2}'.format(queue_line_id.id, product_queue_id,
                                                       message))
                        if log_id:
                            queue_line_id.write({'state': "failed"})
                        continue

                woo_categories = result.get('categories')
                categ_ids = self.woo_sync_categ_with_product_v3(instance, common_log_id,
                                                                woo_categories,
                                                                sync_images_with_product)

                woo_tags = result.get('tags')
                tag_ids = self.woo_sync_tags_with_product_v3(wcapi, instance, common_log_id,
                                                             model_id, woo_tags)
                if not woo_product:
                    if not woo_template:
                        tmpl_info.update({
                            'product_tmpl_id': odoo_product.product_tmpl_id.id,
                            'woo_instance_id': instance.id,
                            'woo_tmpl_id': woo_tmpl_id, 'taxable': taxable,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'exported_in_woo': True,
                            'woo_product_type': result.get('type', ''),
                            'total_variants_in_woo': 1
                        })

                        woo_template = self.create(tmpl_info)
                    variant_info = {
                        'name': template_title, 'default_code': sku,
                        'created_at': template_created_at,
                        'updated_at': template_updated_at,
                        'product_id': odoo_product.id,
                        'woo_is_manage_stock': woo_is_manage_stock,
                        'variant_id': woo_tmpl_id, 'woo_template_id': woo_template.id,
                        'woo_instance_id': instance.id, 'exported_in_woo': True
                    }
                    woo_product = woo_product_obj.create(variant_info)
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', instance.woo_pricelist_id.id),
                             ('product_id', '=', odoo_product.id)], limit=1)
                        if not pricelist_item:
                            instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': odoo_product.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
                else:
                    if not updated_template:
                        tmpl_info.update({
                            'woo_tmpl_id': woo_tmpl_id, 'taxable': taxable,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'exported_in_woo': True,
                            'woo_product_type': result.get('type', ''),
                            'total_variants_in_woo': 1
                        })
                        updated_template = True
                        if not woo_template:
                            woo_template = woo_product.woo_template_id

                        woo_template.write(tmpl_info)
                    variant_info = {
                        'name': template_title, 'default_code': sku,
                        'created_at': template_created_at,
                        'updated_at': template_updated_at,
                        'variant_id': woo_tmpl_id, 'woo_template_id': woo_template.id,
                        'woo_instance_id': instance.id,
                        'woo_is_manage_stock': woo_is_manage_stock,
                        'exported_in_woo': True
                    }
                    woo_product.write(variant_info)
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', instance.woo_pricelist_id.id),
                             ('product_id', '=', woo_product.product_id.id)], limit=1)
                        if not pricelist_item:
                            instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': woo_product.product_id.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
            if is_importable and woo_template and sync_images_with_product:
                if not instance.woo_is_image_url and result.get('variations'):
                    if odoo_product_images:
                        common_product_image_obj.set_product_variant_images(odoo_product_images)
                common_product_image_obj.woo_sync_product_images(instance, result, woo_template,
                                                                 odoo_product_images)

            if woo_template and not import_for_order:
                queue_line_id.write({'state': 'done'})
                _logger.info(
                    'Process Complete Product Queue Line {0} of Product Queue {1}'.format(
                        queue_line_id.id, product_queue_id))
            self._cr.commit()
        if not import_for_order:
            for result in product_data_queue:
                if product_queue_id not in product_queue_dict.keys():
                    product_queue_dict.update({
                        product_queue_id: result.common_log_lines_ids.ids
                    })
                else:
                    product_queue_dict[
                        product_queue_id] += result.common_log_lines_ids.ids
        if not common_log_id.log_lines:
            common_log_id.sudo().unlink()
        return True

    @api.model
    def prepare_woo_template_vals(self, template_data, odoo_template_id, import_for_order,
                                  woo_instance, common_log_book_id):
        """
        Creates new Woo template.
        @author: Maulik Barad on Date 05-Dec-2019.
        @param template_data: Dictionary of template data.
        @param odoo_template_id:Odoo template id to give relation.
        @param import_for_order: True when importing product while order process. 
        @param woo_instance: Instance of Woo.
        @param common_log_book_id: Id of Common Log Book.
        """
        if import_for_order:
            woo_category_ids = self.sync_woo_categ_with_product_v1_v2_v3(woo_instance,
                                                                         common_log_book_id,
                                                                         template_data[
                                                                             "woo_categ_ids"],
                                                                         woo_instance.sync_images_with_product)
            woo_tag_ids = self.sync_woo_tags_with_product_v1_v2_v3(woo_instance,
                                                                   template_data["woo_tag_ids"])
        else:
            woo_category_ids = []
            woo_tag_ids = []
            for woo_category in template_data["woo_categ_ids"]:
                woo_categ = self.env["woo.product.categ.ept"].search(
                    [("woo_categ_id", "=", woo_category.get("id")),
                     ('woo_instance_id', '=', woo_instance.id)], limit=1).id
                woo_category_ids.append(woo_categ)
            for woo_tag in template_data["woo_tag_ids"]:
                product_tag = self.env["woo.tags.ept"].search(
                    [("woo_tag_id", "=", woo_tag.get("id")),
                     ('woo_instance_id', '=', woo_instance.id)], limit=1).id
                woo_tag_ids.append(product_tag)

        template_data.update({
            "product_tmpl_id": odoo_template_id,
            "exported_in_woo": True,
            "woo_categ_ids": [(6, 0, woo_category_ids)],
            "woo_tag_ids": [(6, 0, woo_tag_ids)]
        })
        return template_data

    @api.model
    def update_product_images(self, template_images, variant_image, woo_template, woo_product,
                              woo_instance, template_image_updated, product_dict=False):
        """
        Imports/Updates images of Woo template and variant.
        @author: Maulik Barad on Date 12-Dec-2019.
        @param template_images: Images data of Woo template.
        @param variant_image: Image data of Woo variant.
        @param woo_template_id: Template in Woo layer.
        @param woo_product_id: Variant in Woo layer.
        @param woo_instance: Instance of Woo.
        @param template_image_updated: True when images of template is updated.
        """
        common_product_image_obj = self.env["common.product.image.ept"]
        woo_product_image_obj = woo_product_images = need_to_remove = self.env[
            "woo.product.image.ept"]

        if not template_image_updated:
            existing_common_template_images = {}

            if not woo_instance.woo_is_image_url:
                for odoo_image in woo_template.product_tmpl_id.ept_image_ids:
                    if not odoo_image.image:
                        continue
                    key = hashlib.md5(odoo_image.image).hexdigest()
                    if not key:
                        continue
                    existing_common_template_images.update({key: odoo_image.id})
                for template_image in template_images:
                    image_id = template_image["id"]
                    url = template_image.get('src')
                    woo_product_image = woo_product_image_obj.search(
                        [("woo_template_id", "=", woo_template.id),
                         ("woo_variant_id", "=", False),
                         ("woo_image_id", "=", image_id)])
                    if not woo_product_image:
                        try:
                            response = requests.get(url, stream=True, verify=False, timeout=10)
                            if response.status_code == 200:
                                image = base64.b64encode(response.content)
                                key = hashlib.md5(image).hexdigest()
                                if key in existing_common_template_images.keys():
                                    woo_product_image = woo_product_image_obj.create({
                                        "woo_template_id": woo_template.id,
                                        "woo_image_id": image_id,
                                        "odoo_image_id": existing_common_template_images[key]})
                                else:
                                    if not woo_template.product_tmpl_id.image_1920:
                                        woo_template.product_tmpl_id.image_1920 = image
                                        common_product_image = woo_template.product_tmpl_id.ept_image_ids.filtered(
                                            lambda x: x.image == woo_template.product_tmpl_id.image_1920)
                                    else:
                                        common_product_image = common_product_image_obj.create({
                                            "name": woo_template.name,
                                            "template_id": woo_template.product_tmpl_id.id,
                                            "image": image,
                                            "url": url})
                                    woo_product_image = woo_product_image_obj.search([
                                        ("woo_template_id", "=", woo_template.id),
                                        ("odoo_image_id", "=", common_product_image.id)])
                                    if woo_product_image:
                                        woo_product_image.woo_image_id = image_id
                        except Exception:
                            pass
                    woo_product_images += woo_product_image
                all_woo_product_images = woo_product_image_obj.search(
                    [("woo_template_id", "=", woo_template.id),
                     ("woo_variant_id", "=", False)])
                need_to_remove += (all_woo_product_images - woo_product_images)
            _logger.info("Images Updated for Template {0}".format(woo_template.name))
        if variant_image:
            existing_common_variant_images = {}
            if not woo_instance.woo_is_image_url:
                for odoo_image in woo_product.product_id.ept_image_ids:
                    if not odoo_image.image:
                        continue
                    key = hashlib.md5(odoo_image.image).hexdigest()
                    if not key:
                        continue
                    existing_common_variant_images.update({key: odoo_image.id})
                image_id = variant_image["id"]
                url = variant_image.get('src')
                woo_product_image = woo_product_image_obj.search(
                    [("woo_variant_id", "=", woo_product.id),
                     ("woo_image_id", "=", image_id)])
                if not woo_product_image:
                    try:
                        response = requests.get(url, stream=True, verify=False, timeout=10)
                        if response.status_code == 200:
                            image = base64.b64encode(response.content)
                            key = hashlib.md5(image).hexdigest()
                            if key in existing_common_variant_images.keys():
                                woo_product_image = woo_product_image_obj.create({
                                    "woo_template_id": woo_template.id,
                                    "woo_variant_id": woo_product.id,
                                    "woo_image_id": image_id,
                                    "odoo_image_id": existing_common_variant_images[key]})
                            else:
                                if not woo_product.product_id.image_1920 or product_dict.get('is_image') == True:
                                    woo_product.product_id.image_1920 = image
                                    common_product_image = woo_product.product_id.ept_image_ids.filtered(
                                        lambda x: x.image == woo_product.product_id.image_1920)
                                else:
                                    common_product_image = common_product_image_obj.create({
                                        "name": woo_template.name,
                                        "template_id": woo_template.product_tmpl_id.id,
                                        "product_id": woo_product.product_id.id,
                                        "image": image,
                                        "url": url})
                                woo_product_image = woo_product_image_obj.search(
                                    [("woo_template_id", "=", woo_template.id),
                                     ("woo_variant_id", "=", woo_product.id),
                                     ("odoo_image_id", "=", common_product_image.id)])
                                if woo_product_image:
                                    woo_product_image.woo_image_id = image_id
                    except Exception:
                        pass
            all_woo_product_images = woo_product_image_obj.search(
                [("woo_template_id", "=", woo_template.id),
                 ("woo_variant_id", "=", woo_product.id)])
            need_to_remove += (all_woo_product_images - woo_product_image)
        need_to_remove.sudo().unlink()
        _logger.info("Images Updated for Variant {0}".format(woo_product.name))
        return True

    @api.model
    def sync_products(self, product_data_queue_lines, woo_instance, common_log_book_id,
                      skip_existing_products=False, order_queue_line=False):
        """
        Creates/Updates products from Woocommerce to Odoo from the product data queue lines.
        @author: Maulik Barad on Date 04-Dec-2019.
        @param product_data_queue_lines: Data queue lines of products or List of responses of product.
        @param woo_instance: Instance of Woo.
        @param common_log_book_id: Id of Common Log Book.
        @param skip_existing_products: True when we don't want to update the existing products.
        @param import_for_order: True when importing product while order process.
        Modify by Haresh Mori on date 31/12/2019 modification adds active_test=False for searching an archived
        product for a webhook process.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]

        queue_counter = 0
        sync_category_and_tags = False
        model_id = common_log_line_obj.get_model_id(self._name)
        update_price = woo_instance.sync_price_with_product
        update_images = woo_instance.sync_images_with_product
        if order_queue_line:
            self.env["woo.process.import.export"].sync_woo_attributes(woo_instance)

        for product_data_queue_line in product_data_queue_lines:
            if queue_counter == 10:
                if not order_queue_line:
                    product_queue_id = product_data_queue_line and \
                                       product_data_queue_line.queue_id or False
                    if product_queue_id:
                        product_queue_id.is_process_queue = True
                self._cr.commit()
                queue_counter = 0
            queue_counter += 1

            line_failed = False  # For not making done the queue line, which is already failed.
            template_updated = False
            template_images_updated = False
            if order_queue_line:
                data = product_data_queue_line
                product_queue_id = "from Order"
                sync_category_and_tags = True
            else:
                product_queue_id = product_data_queue_line.queue_id.id
                if product_data_queue_line.queue_id.created_by == "webhook":
                    sync_category_and_tags = True
                data = json.loads(product_data_queue_line.woo_synced_data)

            woo_product_template_id = data.get("id")
            woo_template = self.with_context(active_test=False).search(
                [("woo_tmpl_id", "=", woo_product_template_id),
                 ("woo_instance_id", "=", woo_instance.id)], limit=1)

            template_title = data.get("name")
            _logger.info(
                "Process started for Product-{0}||{1}||Queue {2}.".format(woo_product_template_id,
                                                                          template_title,
                                                                          product_queue_id if order_queue_line else
                                                                          product_data_queue_line.queue_id.name))
            template_info = {
                "name": template_title,
                "woo_tmpl_id": woo_product_template_id,
                "woo_instance_id": woo_instance.id,
                "updated_at": data.get("date_modified").replace("T", " "),
                "woo_short_description": data.get("short_description", ""),
                "woo_description": data.get("description", ""),
                "website_published": True if data["status"] == "publish" else False,
                "taxable": True if data["tax_status"] == "taxable" else False,
                "woo_categ_ids": data.get("categories"),
                "woo_tag_ids": data.get("tags"),
                "total_variants_in_woo": len(data["variations"]),
                "woo_product_type": data["type"],
                "active": True
            }
            if data.get("date_created"):
                template_info.update({"created_at": data.get("date_created").replace("T", " ")})

            available_woo_products = {}
            available_odoo_products = {}
            odoo_template = woo_template.product_tmpl_id
            for variant in data["variations"]:
                woo_product, odoo_product = self.search_odoo_product_variant(woo_instance,
                                                                             variant["sku"],
                                                                             variant["id"])
                if woo_product:
                    available_woo_products.update({variant["id"]: woo_product})
                    woo_template = woo_product.woo_template_id
                if odoo_product:
                    available_odoo_products.update({variant["id"]: odoo_product})
                    odoo_template = odoo_product.product_tmpl_id
                woo_product = odoo_product = False
            product_dict = {}
            if data["variations"]:
                for variant in data["variations"]:
                    variant_id = variant.get("id")
                    product_sku = variant.get("sku")
                    variant_price = variant.get("regular_price") or variant.get("sale_price") or 0.0

                    woo_product = available_woo_products.get(variant_id)
                    odoo_product = False
                    if woo_product:
                        odoo_product = woo_product.product_id
                        # Do not update already imported product.
                        if skip_existing_products:
                            continue

                    # Checks for if the product is importable or not by checking the attributes.
                    is_importable, message = self.is_product_importable(data, woo_instance,
                                                                        odoo_product, woo_product)
                    if not is_importable:
                        common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                        product_data_queue_line if not order_queue_line
                                                                        else order_queue_line,
                                                                        common_log_book_id)
                        _logger.info(
                            "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                                woo_product_template_id, product_queue_id, message))
                        if not order_queue_line:
                            product_data_queue_line.state = "failed"
                            line_failed = True
                        break

                    if not product_sku:
                        message = "No SKU found for a Variant of {0}.".format(template_title)
                        common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                        product_data_queue_line if not order_queue_line
                                                                        else order_queue_line,
                                                                        common_log_book_id)
                        _logger.info(
                            "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                                woo_product_template_id, product_queue_id, message))
                        continue

                    variant_info = {
                        "name": template_title, "default_code": product_sku,
                        "variant_id": variant_id, "woo_instance_id": woo_instance.id,
                        "exported_in_woo": True,
                        "product_url": variant.get("permalink", ""),
                        "woo_is_manage_stock": variant["manage_stock"],
                        "updated_at": variant.get("date_modified").replace("T", " "),
                        "active": True
                    }
                    # As the date_created field will be empty, when product is not published.
                    if variant.get("date_created"):
                        variant_info.update(
                            {"created_at": variant.get("date_created").replace("T", " ")})

                    if not woo_product:
                        if not woo_template:
                            if not odoo_template and woo_instance.auto_import_product:
                                odoo_template, available_odoo_products = self.woo_create_variant_product(
                                    data, woo_instance)
                            if not odoo_template:
                                message = "%s Template Not found for sku %s in Odoo." % (
                                    template_title, product_sku)
                                common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                                product_data_queue_line if not
                                                                                order_queue_line else order_queue_line,
                                                                                common_log_book_id)
                                _logger.info(
                                    "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                                        woo_product_template_id, product_queue_id, message))
                                if not order_queue_line:
                                    product_data_queue_line.state = "failed"
                                    line_failed = True
                                break

                            woo_template_vals = self.prepare_woo_template_vals(template_info,
                                                                               odoo_template.id,
                                                                               sync_category_and_tags,
                                                                               woo_instance,
                                                                               common_log_book_id)
                            woo_template = self.create(woo_template_vals)
                        elif not template_updated:
                            woo_template_vals = self.prepare_woo_template_vals(template_info,
                                                                               odoo_template.id,
                                                                               sync_category_and_tags,
                                                                               woo_instance,
                                                                               common_log_book_id)
                            woo_template.write(woo_template_vals)
                        template_updated = True

                        odoo_product = available_odoo_products.get(variant_id)
                        if not odoo_product:
                            if not woo_instance.auto_import_product:
                                message = "Product %s Not found for sku %s in Odoo." % (
                                    template_title, product_sku)
                                common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                                product_data_queue_line if not
                                                                                order_queue_line else order_queue_line,
                                                                                common_log_book_id)
                                _logger.info(
                                    "Product {0} Not found for sku {1} of Queue {2} in Odoo.".format(
                                        template_title, product_sku, product_queue_id))
                                if not order_queue_line:
                                    product_data_queue_line.state = "failed"
                                    line_failed = True
                                continue

                            if odoo_template.attribute_line_ids:
                                # If the new variant has other attribute than available in odoo template, then exception
                                # activity will be generated.
                                # else it will add new value in current attribute, and will relate with the new odoo
                                # variant.
                                woo_attribute_ids = []
                                odoo_attributes = odoo_template.attribute_line_ids.attribute_id.ids
                                for attribute in variant.get("attributes"):
                                    attribute = self.env["product.attribute"].get_attribute(
                                        attribute["name"])
                                    woo_attribute_ids.append(attribute.id)
                                woo_attribute_ids.sort()
                                odoo_attributes.sort()
                                if odoo_attributes != woo_attribute_ids:
                                    message = "- Product %s has tried adding a new attribute for sku '%s' in Odoo.\n- " \
                                              "System will not allow adding new attributes to a product." % (
                                                  template_title, product_sku)
                                    common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                                    product_data_queue_line if not
                                                                                    order_queue_line else order_queue_line,
                                                                                    common_log_book_id)
                                    _logger.info(
                                        "Product {0} has tried to add new attribute for sku {1} of Queue {2} in Odoo. "
                                        "Please check activity for this.".format(
                                            template_title, product_sku, product_queue_id))

                                    if not order_queue_line:
                                        product_data_queue_line.state = "failed"
                                        line_failed = True
                                    if woo_instance.is_create_schedule_activity:
                                        common_log_book_id.create_woo_schedule_activity()
                                    break
                                else:
                                    template_attribute_value_domain = self.find_template_attribute_values(
                                        data.get("attributes"), variant.get("attributes"),
                                        odoo_template, woo_instance)
                                    if not template_attribute_value_domain:
                                        for woo_attribute in variant.get("attributes"):
                                            #                                         attribute_id =
                                            #                                         woo_attributes.filtered(lambda x:
                                            #                                         x.woo_attribute_id ==
                                            #                                         woo_attribute["id"]).attribute_id.id
                                            attribute_id = self.env["product.attribute"].get_attribute(
                                                woo_attribute["name"],
                                                type="radio",
                                                create_variant="always",
                                                auto_create=True)
                                            #                                         woo_attribute_val = self.env[
                                            #                                         "woo.product.attribute.term.ept"].search([("woo_attribute_id", "=", woo_attribute["id"]), ("slug", "=ilike", woo_attribute["option"])], limit=1)
                                            #                                         value_id =
                                            #                                         woo_attribute_val.attribute_value_id.id
                                            value_id = self.env[
                                                "product.attribute.value"].get_attribute_values(
                                                woo_attribute["option"],
                                                attribute_id.id,
                                                auto_create=True)
                                            attribute_line = odoo_template.attribute_line_ids.filtered(
                                                lambda x: x.attribute_id.id == attribute_id.id)
                                            if not value_id.id in attribute_line.value_ids.ids:
                                                attribute_line.value_ids = [(4, value_id.id, False)]
                                        odoo_template._create_variant_ids()
                                        template_attribute_value_domain = self.find_template_attribute_values(
                                            data.get("attributes"), variant.get("attributes"),
                                            odoo_template, woo_instance)
                                    template_attribute_value_domain.append(
                                        ("product_tmpl_id", "=", odoo_template.id))
                                    odoo_product = self.env["product.product"].search(
                                        template_attribute_value_domain)
                                    odoo_product.default_code = variant["sku"]
                            else:
                                template_vals = {"name": template_title, "type": "product",
                                                 "default_code": variant["sku"]}
                                if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                                    template_vals.update({"description_sale": variant.get("description", "")})
                                # self.env["product.template"].create(template_vals)
                                odoo_product = self.env["product.product"].search(
                                    [("default_code", "=", variant["sku"])])
                                if not odoo_product:
                                    odoo_product = self.env["product.product"].create(template_vals)
                                else:
                                    odoo_product.write(template_vals)
                        if odoo_product:
                            variant_info.update({"product_id": odoo_product.id,
                                             "woo_template_id": woo_template.id})
                            woo_product = self.env["woo.product.product.ept"].create(variant_info)
                            woo_template.product_tmpl_id = odoo_product.product_tmpl_id
                        else:
                            message = "- Product Template %s  was found, but its related variant with attribute %s was not found." % (
                                          template_title, variant['attributes'][0]['name'])
                            common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                            product_data_queue_line if not
                                                                            order_queue_line else order_queue_line,
                                                                            common_log_book_id)
                            _logger.info(
                                "- Product Template {0}  was found, but its related variant with attribute {1} was not found.".format(
                                    template_title, variant['attributes'][0]['name']))
                            continue
                    else:
                        if not template_updated:
                            woo_template_vals = self.prepare_woo_template_vals(template_info,
                                                                               woo_product.product_id.product_tmpl_id.id,
                                                                               sync_category_and_tags,
                                                                               woo_instance,
                                                                               common_log_book_id)
                            woo_template.write(woo_template_vals)
                            template_updated = True
                        woo_product.write(variant_info)
                    if update_price:
                        woo_instance.woo_pricelist_id.set_product_price_ept(woo_product.product_id.id,
                                                                            variant_price)
                    if update_images:
                        if not woo_template.product_tmpl_id.image_1920:
                            product_dict.update({'product_tmpl_id': woo_template.product_tmpl_id, 'is_image': True})
                        self.update_product_images(data["images"], variant["image"], woo_template,
                                                   woo_product, woo_instance, template_images_updated, product_dict)
                        template_images_updated = True
            else :
                product_sku = data["sku"]
                variant_price = data.get("regular_price") or data.get("sale_price") or 0.0
                if not product_sku:
                    message = "Value of SKU/Internal Reference is not set for product '{0}'" \
                              ", in the Woocommerce store.".format(template_title)
                    common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                    product_data_queue_line if not order_queue_line
                                                                    else order_queue_line,
                                                                    common_log_book_id)
                    _logger.info(
                        "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                            woo_product_template_id, product_queue_id, message))
                    if not order_queue_line:
                        product_data_queue_line.write(
                            {"state": "failed", "last_process_date": datetime.now()})
                        line_failed = True
                    continue

                woo_product, odoo_product = self.search_odoo_product_variant(woo_instance,
                                                                             product_sku,
                                                                             woo_product_template_id)

                if woo_product and not odoo_product:
                    woo_template = woo_product.woo_template_id
                    odoo_product = woo_product.product_id
                    # Skip already imported product.
                    if skip_existing_products:
                        product_data_queue_line.state = "done"
                        continue

                if odoo_product:
                    odoo_template = odoo_product.product_tmpl_id

                is_importable, message = self.is_product_importable(data, woo_instance,
                                                                    odoo_product, woo_product)
                if not is_importable:
                    common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                    product_data_queue_line if not order_queue_line
                                                                    else order_queue_line,
                                                                    common_log_book_id)
                    _logger.info(
                        "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                            woo_product_template_id, product_queue_id, message))
                    if not order_queue_line:
                        product_data_queue_line.state = "failed"
                        line_failed = True
                    continue

                variant_info = {
                    "name": template_title, "default_code": product_sku,
                    "variant_id": woo_product_template_id, "woo_instance_id": woo_instance.id,
                    "exported_in_woo": True,
                    "product_url": data.get("permalink", ""),
                    "woo_is_manage_stock": data["manage_stock"],
                    "updated_at": data.get("date_modified").replace("T", " "),
                    "active": True
                }
                if data.get("date_created"):
                    variant_info.update({"created_at": data.get("date_created").replace("T", " ")})

                if not woo_product:
                    if not woo_template:
                        if not odoo_template and woo_instance.auto_import_product:
                            woo_weight = float(data.get("weight") or "0.0")
                            weight = self.convert_weight_by_uom(woo_weight, woo_instance, import_process=True)
                            template_vals = {
                                "name": template_title,
                                "type": "product",
                                "default_code": data["sku"],
                                "weight":weight,
                            }
                            if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                                template_vals.update({"description_sale": data.get("description", "")})

                            odoo_template = self.env["product.template"].create(template_vals)
                            odoo_product = odoo_template.product_variant_ids
                        if not odoo_template:
                            message = "%s Template Not found for sku %s in Odoo." % (
                                template_title, product_sku)
                            common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                            product_data_queue_line if not
                                                                            order_queue_line else order_queue_line,
                                                                            common_log_book_id)
                            _logger.info(
                                "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                                    woo_product_template_id, product_queue_id, message))
                            if not order_queue_line:
                                product_data_queue_line.state = "failed"
                                line_failed = True
                            continue

                        woo_template_vals = self.prepare_woo_template_vals(template_info,
                                                                           odoo_template.id,
                                                                           sync_category_and_tags,
                                                                           woo_instance,
                                                                           common_log_book_id)
                        woo_template = self.create(woo_template_vals)
                        template_updated = True

                    variant_info.update(
                        {"product_id": odoo_product.id, "woo_template_id": woo_template.id})
                    woo_product = self.env["woo.product.product.ept"].create(variant_info)
                else:
                    if not template_updated:
                        woo_template_vals = self.prepare_woo_template_vals(template_info,
                                                                           woo_template.product_tmpl_id.id,
                                                                           sync_category_and_tags,
                                                                           woo_instance,
                                                                           common_log_book_id)
                        woo_template.write(woo_template_vals)
                        template_updated = True
                    woo_product.write(variant_info)
                if update_price:
                    woo_instance.woo_pricelist_id.set_product_price_ept(woo_product.product_id.id,
                                                                        variant_price)
                if update_images:
                    self.update_product_images(data["images"], {}, woo_template, woo_product,
                                               woo_instance, template_images_updated)
                    template_images_updated = True
            if not order_queue_line:
                if woo_template and not line_failed:
                    product_data_queue_line.write({"state": "done",
                                                   "last_process_date": datetime.now()})
                else:
                    message = "Misconfiguration at Woocommerce store for product named - '%s'.\n " \
                              "- It seems this might be a variation product, but variations are " \
                              "not defined at store." % (template_title)
                    common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                    product_data_queue_line if not order_queue_line
                                                                    else order_queue_line,
                                                                    common_log_book_id)
                    _logger.info(
                        "Process Failed of Product {0}||Queue {1}||Reason is {2}".format(
                            woo_product_template_id, product_queue_id, message))
                    product_data_queue_line.write(
                        {"state": "failed", "last_process_date": datetime.now()})
                    # Below two-line add by Haresh on date 6/1/2020 to manage the which queue is running in the background
                    product_data_queue_line.queue_id.is_process_queue = False
            _logger.info(
                "Process done for Product-{0}||{1}||Queue {2}.".format(woo_product_template_id,
                                                                       template_title,
                                                                       product_queue_id if order_queue_line else
                                                                       product_data_queue_line.queue_id.name))
        return True

    def woo_sync_products_v1_v2_v3(self, product_data_queue, woo_instance, import_for_order=False,
                                   update_price=False, sync_images_with_product=False,
                                   skip_existing_products=False, update_templates=True):
        woo_common_log_obj = self.env["common.log.book.ept"]
        process_import_export_obj = self.env['woo.process.import.export']
        if woo_instance.woo_attribute_type == 'select' and not import_for_order:
            process_import_export_obj.sync_woo_attributes(woo_instance)
        woo_product_obj = self.env['woo.product.product.ept']
        common_log_line_obj = self.env["common.log.lines.ept"]
        common_product_image_obj = self.env["common.product.image.ept"]
        product_template_obj = self.env['product.template']
        odoo_product_variant_obj = self.env['product.product']
        model_id = common_log_line_obj.get_model_id("woo.product.template.ept")
        product_queue_dict = {}
        result = False
        categ_ids = tag_ids = odoo_product_images = []
        categ_and_tag_imported = True
        woo_common_log_id = woo_common_log_obj.create(
            {
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': woo_instance.id,
                'active': True,
            })
        if not import_for_order:
            product_queue_id = product_data_queue[0].queue_id.id
            _logger.info(
                'Start Product Sync Processing of Product Queue {}'.format(product_queue_id))
        if import_for_order:
            categ_and_tag_imported = False

        if categ_and_tag_imported:
            process_import_export_obj.sync_woo_product_category(woo_instance)
            process_import_export_obj.sync_product_tags(woo_instance)
        for result in product_data_queue:
            if not import_for_order:
                product_queue_id = result.queue_id.id
                _logger.info(
                    'Process Start of Product Queue Line {0} of Product Queue {1}'.format(
                        result.id,
                        product_queue_id))
                woo_product_template_info = json.loads(result.woo_synced_data)
            else:
                woo_product_template_info = result
            woo_product = odoo_product = updated_template = is_importable = onetime_call = website_published = False
            taxable = True
            woo_product_template_id = woo_product_template_info.get('id')
            template_title = woo_product_template_info.get('name')
            template_created_at = woo_product_template_info.get('date_created')
            template_updated_at = woo_product_template_info.get('date_modified')

            if template_created_at and template_created_at.startswith('-'):
                template_created_at = template_created_at[1:]
            if template_updated_at and template_updated_at.startswith('-'):
                template_updated_at = template_updated_at[1:]

            template_created_at = datetime.strptime(template_created_at,
                                                    "%Y-%m-%dT%H:%M:%S").strftime(
                "%Y-%m-%d %H:%M:%S") if template_created_at else ''
            template_updated_at = datetime.strptime(template_updated_at,
                                                    "%Y-%m-%dT%H:%M:%S").strftime(
                "%Y-%m-%d %H:%M:%S") if template_created_at else ''
            short_description = woo_product_template_info.get('short_description')
            description = woo_product_template_info.get('description')
            status = woo_product_template_info.get('status')
            tax_status = woo_product_template_info.get('tax_status')

            woo_template = self.search(
                [('woo_tmpl_id', '=', woo_product_template_id),
                 ('woo_instance_id', '=', woo_instance.id)],
                limit=1)
            if woo_template and not update_templates:
                continue

            if tax_status != 'taxable':
                taxable = False

            if status == 'publish':
                website_published = True

            template_info = {
                'name': template_title, 'created_at': template_created_at or False,
                'updated_at': template_updated_at or False,
                'woo_short_description': short_description,
                'woo_description': description,
                'website_published': website_published, 'taxable': taxable
            }

            for woo_product_variantion_info in woo_product_template_info.get('variations'):
                variant_id = woo_product_variantion_info.get('id')
                product_url = woo_product_variantion_info.get('permalink', False)
                product_sku = woo_product_variantion_info.get('sku')
                woo_is_manage_stock = True if woo_product_variantion_info.get(
                    'manage_stock') else False
                woo_product, odoo_product = self.search_odoo_product_variant(woo_instance,
                                                                             product_sku,
                                                                             variant_id)
                if woo_product and not odoo_product:
                    odoo_product = woo_product.product_id
                    # Added code for skip the product sync if already product imported
                    if skip_existing_products:
                        continue

                is_importable = True
                message = ""

                is_importable, message = self.is_product_importable(woo_product_template_info,
                                                                    woo_instance, odoo_product,
                                                                    woo_product)
                if not is_importable:
                    log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                             model_id,
                                                                             result)
                    if not import_for_order:
                        _logger.info(
                            'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                            'Reason is {2}'.format(result.id, product_queue_id, message))
                    if log_id:
                        result.write({'state': "failed"})
                    break

                if not odoo_product and not woo_product and not woo_template:
                    if product_sku and woo_instance.auto_import_product:
                        if not onetime_call:
                            self.woo_create_variant_product(woo_product_template_info, woo_instance)
                            odoo_product = odoo_product_variant_obj.search(
                                [('default_code', '=', product_sku)], limit=1)
                            onetime_call = True
                    else:
                        message = "%s Product Not found for sku %s" % (template_title, product_sku)
                        log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                 model_id,
                                                                                 result)
                        if not import_for_order:
                            _logger.info(
                                'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                'Reason is {2}'.format(result.id, product_queue_id, message))
                        if log_id:
                            result.write({'state': "failed"})
                        continue

                if not odoo_product:
                    continue
                variant_info = {}
                price = woo_product_variantion_info.get(
                    'regular_price') or woo_product_variantion_info.get(
                    'sale_price') or 0.0
                var_image_id = False
                var_image_src = var_img = ''
                if sync_images_with_product:
                    var_images = woo_product_variantion_info.get('image')
                    if woo_instance.woo_version != 'v3':
                        var_images = [var_images]
                    for var_image in var_images:
                        if var_image is not None:
                            if str(var_image.get('name').encode(
                                    'utf-8')) == 'Placeholder' or not var_image.get('id'):
                                continue
                            if var_image.get(
                                    'position') == 0 or woo_instance.woo_version == 'wc/v3':
                                var_image_src = var_image.get('src')
                                var_image_id = var_image.get('id')
                                if not woo_instance.woo_is_image_url and var_image_src:
                                    try:
                                        res_img = requests.get(var_image_src, stream=True,
                                                               verify=False,
                                                               timeout=10)
                                        if res_img.status_code == 200:
                                            var_img = base64.b64encode(res_img.content)
                                    except Exception:
                                        pass

                created_at = woo_product_variantion_info.get('date_created')
                updated_at = woo_product_variantion_info.get('date_modified')
                if created_at and created_at.startswith('-'):
                    created_at = created_at[1:]
                if updated_at and updated_at.startswith('-'):
                    updated_at = updated_at[1:]

                created_at = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S").strftime(
                    "%Y-%m-%d %H:%M:%S") if created_at else ''
                updated_at = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S").strftime(
                    "%Y-%m-%d %H:%M:%S") if created_at else ''
                variant_info = {
                    'name': template_title, 'default_code': product_sku,
                    'created_at': created_at or False,
                    'updated_at': updated_at or False,
                    'product_url': product_url or False
                }
                if woo_instance.woo_is_image_url and sync_images_with_product:
                    variant_info.update(
                        {'response_url': var_image_src, 'woo_image_id': var_image_id})
                if not woo_product:
                    if not woo_template:
                        woo_categories = woo_product_template_info.get('categories')
                        if not categ_and_tag_imported:
                            categ_ids = self.sync_woo_categ_with_product_v1_v2_v3(woo_instance,
                                                                                  woo_common_log_id,
                                                                                  woo_categories,
                                                                                  sync_images_with_product)
                        else:
                            woo_categs = []
                            for woo_category in woo_categories:
                                woo_categ = woo_category.get('id') and self.env[
                                    'woo.product.categ.ept'].search(
                                    [('woo_categ_id', '=', woo_category.get('id'))], limit=1)
                                woo_categ and woo_categs.append(woo_categ.id)
                            categ_ids = woo_categs and woo_categs or []
                        woo_tags = woo_product_template_info.get('tags')
                        if not categ_and_tag_imported:
                            tag_ids = self.sync_woo_tags_with_product_v1_v2_v3(woo_instance,
                                                                               woo_tags)
                        else:
                            product_tags = []
                            for woo_tag in woo_tags:
                                product_tag = woo_tag.get('id') and self.env['woo.tags.ept'].search(
                                    [('woo_tag_id', '=', woo_tag.get('id'))], limit=1)
                                product_tag and product_tags.append(product_tag.id)
                            tag_ids = product_tags and product_tags or []
                        template_info.update({
                            'product_tmpl_id': odoo_product.product_tmpl_id.id,
                            'woo_instance_id': woo_instance.id,
                            'woo_tmpl_id': woo_product_template_id,
                            'taxable': taxable,
                            'exported_in_woo': True,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'total_variants_in_woo': len(
                                woo_product_template_info.get('variations')),
                            'woo_product_type': woo_product_template_info.get(
                                'type', ''),
                        })
                        woo_template_obj = self.env['woo.product.template.ept']
                        woo_template = woo_template_obj.create(template_info)

                    variant_info.update(
                        {
                            'product_id': odoo_product.id,
                            'name': template_title,
                            'variant_id': variant_id,
                            'woo_template_id': woo_template.id,
                            'woo_instance_id': woo_instance.id,
                            'exported_in_woo': True,
                            'product_url': product_url,
                            'woo_is_manage_stock': woo_is_manage_stock,
                        })
                    woo_product = woo_product_obj.create(variant_info)
                    if not woo_instance.woo_is_image_url and sync_images_with_product:
                        odoo_product_images.append({
                            'odoo_product': odoo_product,
                            'image': var_img if woo_product else None,
                            'sku': product_sku, 'image_id': var_image_id
                        })
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                             ('product_id', '=', odoo_product.id)], limit=1)

                        if not pricelist_item:
                            woo_instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': odoo_product.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
                else:
                    if not updated_template:
                        woo_categories = woo_product_template_info.get('categories')
                        if not categ_and_tag_imported:
                            categ_ids = self.sync_woo_categ_with_product_v1_v2_v3(woo_instance,
                                                                                  woo_common_log_id,
                                                                                  woo_categories,
                                                                                  sync_images_with_product)
                        else:
                            woo_categs = []
                            for woo_category in woo_categories:
                                woo_categ = woo_category.get('id') and self.env[
                                    'woo.product.categ.ept'].search(
                                    [('woo_categ_id', '=', woo_category.get('id'))], limit=1)
                                woo_categ and woo_categs.append(woo_categ.id)
                            categ_ids = woo_categs and woo_categs or []

                        woo_tags = woo_product_template_info.get('tags')
                        if not categ_and_tag_imported:
                            tag_ids = self.sync_woo_tags_with_product_v1_v2_v3(woo_instance,
                                                                               woo_tags)
                        else:
                            product_tags = []
                            for woo_tag in woo_tags:
                                product_tag = woo_tag.get('id') and self.env['woo.tags.ept'].search(
                                    [('woo_tag_id', '=', woo_tag.get('id'))], limit=1)
                                product_tag and product_tags.append(product_tag.id)
                            tag_ids = product_tags and product_tags or []
                        template_info.update({
                            'woo_tmpl_id': woo_product_template_id, 'taxable': taxable,
                            'exported_in_woo': True,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'woo_product_type': woo_product_template_info.get(
                                'type', ''),
                            'total_variants_in_woo': len(
                                woo_product_template_info.get('variations'))
                        })
                        updated_template = True
                        if not woo_template:
                            woo_template = woo_product.woo_template_id
                        woo_template.write(template_info)
                    variant_info.update({
                        'variant_id': variant_id,
                        'woo_template_id': woo_template.id,
                        'woo_instance_id': woo_instance.id,
                        'exported_in_woo': True,
                        'woo_is_manage_stock': woo_is_manage_stock
                    })
                    woo_product.write(variant_info)
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                             ('product_id', '=', woo_product.product_id.id)], limit=1)
                        if not pricelist_item:
                            woo_instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': woo_product.product_id.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})

                    if not woo_instance.woo_is_image_url and sync_images_with_product:
                        odoo_product_images.append({
                            'odoo_product': odoo_product,
                            'image': var_img if woo_product else None,
                            'sku': product_sku
                        })
                        if var_img:
                            odoo_product.image_1920 = var_img
            if not woo_product_template_info.get('variations'):
                is_importable = True
                sku = woo_product_template_info.get('sku')
                product_url = woo_product_template_info.get('permalink', False)
                woo_is_manage_stock = True if woo_product_template_info.get(
                    'manage_stock') else False
                price = woo_product_template_info.get(
                    'regular_price') or woo_product_template_info.get('sale_price') or 0.0
                woo_product, odoo_product = self.search_odoo_product_variant(woo_instance, sku,
                                                                             woo_product_template_id)

                if woo_product:
                    odoo_product = woo_product.product_id
                is_importable, message = self.is_product_importable(woo_product_template_info,
                                                                    woo_instance, odoo_product,
                                                                    woo_product)
                if not is_importable:
                    log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                             model_id,
                                                                             result)
                    if not import_for_order:
                        _logger.info(
                            'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                            'Reason is {2}'.format(result.id, product_queue_id, message))
                    if log_id:
                        result.write({'state': "failed"})
                    continue

                if not odoo_product and not woo_product and not woo_template:
                    if sku:
                        if woo_instance.auto_import_product:
                            vals = {
                                'name': template_title,
                                'default_code': sku,
                                'type': 'product'
                            }
                            product_template = product_template_obj.create(vals)
                            odoo_product = product_template.product_variant_ids
                            if woo_instance.sync_price_with_product:
                                pricelist_item = self.env['product.pricelist.item'].search(
                                    [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                                     ('product_id', '=', odoo_product.id)], limit=1)
                                if not pricelist_item:
                                    woo_instance.woo_pricelist_id.write({
                                        'item_ids': [(0, 0, {
                                            'applied_on': '0_product_variant',
                                            'product_id': odoo_product.id,
                                            'compute_price': 'fixed',
                                            'fixed_price': price
                                        })]
                                    })
                                else:
                                    if pricelist_item.currency_id.id != product_template.company_id.currency_id.id:
                                        instance_currency = pricelist_item.currency_id
                                        product_company_currency = product_template.company_id.currency_id
                                        price = instance_currency.compute(float(price),
                                                                          product_company_currency)
                                    pricelist_item and pricelist_item.write(
                                        {'fixed_price': price})
                                odoo_product.write({'list_price': price})
                        else:
                            message = "%s Product  Not found for sku %s" % (template_title, sku)
                            log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                     model_id,
                                                                                     result)
                            if not import_for_order:
                                _logger.info(
                                    'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                    'Reason is {2}'.format(result.id, product_queue_id,
                                                           message))
                            if log_id:
                                result.write({'state': "failed"})
                            continue
                    else:
                        message = "SKU not set in Product: %s and ID: %s." % (
                            template_title, woo_product_template_info.get('id'))
                        log_id = common_log_line_obj.woo_create_product_log_line(message,
                                                                                 model_id,
                                                                                 result)
                        if not import_for_order:
                            _logger.info(
                                'Process Failed of Product Queue Line {0} of Product Queue {1} and '
                                'Reason is {2}'.format(result.id, product_queue_id, message))
                        if log_id:
                            result.write({'state': "failed"})
                        continue
                woo_categories = woo_product_template_info.get('categories')
                if not categ_and_tag_imported:
                    categ_ids = self.sync_woo_categ_with_product_v1_v2_v3(woo_instance,
                                                                          woo_common_log_id,
                                                                          woo_categories,
                                                                          sync_images_with_product)
                else:
                    woo_categs = []
                    for woo_category in woo_categories:
                        woo_categ = woo_category.get('id') and self.env[
                            'woo.product.categ.ept'].search(
                            [('woo_categ_id', '=', woo_category.get('id'))], limit=1)
                        woo_categ and woo_categs.append(woo_categ.id)
                    categ_ids = woo_categs and woo_categs or []

                woo_tags = woo_product_template_info.get('tags')
                if not categ_and_tag_imported:
                    tag_ids = self.sync_woo_tags_with_product_v1_v2_v3(woo_instance, woo_tags)
                else:
                    product_tags = []
                    for woo_tag in woo_tags:
                        product_tag = woo_tag.get('id') and self.env['woo.tags.ept'].search(
                            [('woo_tag_id', '=', woo_tag.get('id'))], limit=1)
                        product_tag and product_tags.append(product_tag.id)
                    tag_ids = product_tags and product_tags or []
                if not woo_product:
                    if not woo_template:
                        template_info.update({
                            'product_tmpl_id': odoo_product.product_tmpl_id.id,
                            'woo_instance_id': woo_instance.id,
                            'woo_tmpl_id': woo_product_template_id,
                            'taxable': taxable,
                            'woo_product_type': woo_product_template_info.get(
                                'type', ''),
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'exported_in_woo': True,
                            'total_variants_in_woo': 1,
                        })
                        woo_template = self.create(template_info)
                    variant_info = {
                        'name': template_title, 'default_code': sku,
                        'created_at': template_created_at,
                        'updated_at': template_updated_at,
                        'product_id': odoo_product.id,
                        'variant_id': woo_product_template_id,
                        'woo_template_id': woo_template.id,
                        'woo_instance_id': woo_instance.id, 'exported_in_woo': True,
                        'product_url': product_url,
                        'woo_is_manage_stock': woo_is_manage_stock
                    }
                    woo_product_obj.create(variant_info)
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                             ('product_id', '=', odoo_product.id)], limit=1)
                        if not pricelist_item:
                            woo_instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': odoo_product.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
                else:
                    if not updated_template:
                        template_info.update({
                            'woo_tmpl_id': woo_product_template_id, 'taxable': taxable,
                            'woo_categ_ids': [(6, 0, categ_ids)],
                            'woo_tag_ids': [(6, 0, tag_ids)],
                            'exported_in_woo': True,
                            'woo_product_type': woo_product_template_info.get('type', ''),
                            'total_variants_in_woo': 1
                        })
                        updated_template = True
                        if not woo_template:
                            woo_template = woo_product.woo_template_id
                        woo_template.write(template_info)
                    variant_info = {
                        'name': template_title, 'default_code': sku,
                        'created_at': template_created_at,
                        'updated_at': template_updated_at,
                        'variant_id': woo_product_template_id,
                        'woo_template_id': woo_template.id,
                        'woo_instance_id': woo_instance.id,
                        'woo_is_manage_stock': woo_is_manage_stock,
                        'exported_in_woo': True
                    }
                    woo_product.write(variant_info)
                    if update_price:
                        pricelist_item = self.env['product.pricelist.item'].search(
                            [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
                             ('product_id', '=', woo_product.product_id.id)], limit=1)
                        if not pricelist_item:
                            woo_instance.woo_pricelist_id.write({
                                'item_ids': [(0, 0, {
                                    'applied_on': '0_product_variant',
                                    'product_id': woo_product.product_id.id,
                                    'compute_price': 'fixed',
                                    'fixed_price': price
                                })]
                            })
                        else:
                            if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
                                instance_currency = pricelist_item.currency_id
                                product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
                                price = instance_currency.compute(float(price),
                                                                  product_company_currency)
                            pricelist_item.write({'fixed_price': price})
            if is_importable and woo_template and sync_images_with_product:
                common_product_image_obj.woo_sync_product_images(woo_instance,
                                                                 woo_product_template_info,
                                                                 woo_template)
                if not woo_instance.woo_is_image_url and woo_product_template_info.get(
                        'variations'):
                    common_product_image_obj.set_product_variant_images(odoo_product_images)
            if woo_template and not import_for_order:
                result.write({'state': "done"})
                _logger.info(
                    'Process Complete Product Queue Line {0} of Product Queue {1}'.format(
                        result.id,
                        product_queue_id))
            self._cr.commit()
        if not import_for_order:
            for result in product_data_queue:
                if product_queue_id not in product_queue_dict.keys():
                    product_queue_dict.update({
                        product_queue_id: result.common_log_lines_ids.ids
                    })
                else:
                    product_queue_dict[
                        product_queue_id] += result.common_log_lines_ids.ids
        if not woo_common_log_id.log_lines:
            woo_common_log_id.sudo().unlink()
        return True

    @api.model
    def update_new_products_in_woo(self, instance, templates, update_price, publish, update_image,
                                   update_basic_detail, common_log_id):
        """
         This method is used for update the product data in woo commerce
        :param instance: It contain the browsable object of the current instance
        :param templates: It contain the browsable object of the woo product template
        :param update_price: It contain wither True or False and its type is Boolean
        :param publish: It contain wither True or False and its type is Boolean
        :param update_image: It contain wither True or False and its type is Boolean
        :param update_basic_detail: It contain wither True or False and its type is Boolean
        :param common_log_id: It contain the log book id and its type is object
        :return: It will return True if the product update process is successfully completed
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        wcapi = instance.woo_connect()

        batches = []

        if len(templates) > 100:
            batches += self.browse(self.prepare_batches(templates.ids))
        else:
            batches.append(templates)

        for templates in batches:
            if instance.woo_version == "v3":
                batch_update = {'products': []}
            else:
                batch_update = {'update': []}
            batch_update_data = []

            for template in templates:
                data = {'id': template.woo_tmpl_id, 'variations': [], "type":template.woo_product_type}
                if not publish:
                    data.update(
                        {'status': 'publish' if template.website_published else 'draft'})
                elif publish == 'publish':
                    data.update({'status': 'publish'})
                else:
                    data.update({'status': 'draft'})
                flag, data = self.get_product_update_data(wcapi, template, instance, update_image,
                                                          update_basic_detail, data, common_log_id,
                                                          model_id)

                data, flag = self.prepare_product_variant_dict(instance, template, data,
                                                               update_basic_detail,
                                                               update_price, update_image,
                                                               common_log_id, model_id)
                flag and batch_update_data.append(data)
                data = {}
            if batch_update_data:
                if instance.woo_version == 'v3':
                    batch_update.update({'products': batch_update_data})
                    res = wcapi.post('products/bulk', batch_update)
                else:
                    batch_update.update({'update': batch_update_data})
                    res = wcapi.post('products/batch', batch_update)
                if not isinstance(res, requests.models.Response):
                    message = "Update Product \nResponse is not in proper format :: %s" % (
                        res)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
                    continue
                if res.status_code not in [200, 201]:
                    message = "Update Product \n%s" % (res.content)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
                    continue
                else:
                    if publish == 'publish':
                        templates.write({'website_published': True})
                    elif publish == 'unpublish':
                        templates.write({'website_published': False})
                try:
                    response = res.json()
                except Exception as e:
                    message = "Json Error : While update products to WooCommerce for instance %s." \
                              " \n%s" % (instance.name, e)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
                    continue
                if response.get('data', {}) and response.get('data', {}).get('status') != 200:
                    message = "Update Product \n%s" % (response.get('message'))
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
                    continue
                for product in response.get("update"):
                    if product.get("error"):
                        message = "Update Product \n%s" % (product.get("error").get('message'))
                        common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                        common_log_id,
                                                                        False)
        return True

    def auto_update_stock(self, ctx):
        """
        This method is call when auto import stock cron in enable
        This method is call update_stock() method which is responsible to update stock in WooCommerce.
        :return: Boolean
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 16-11-2019.
        :Task id: 156886
        """
        woo_instance_id = ctx.get('woo_instance_id', False)
        instance = self.woo_instance_id.browse(woo_instance_id)
        self.update_stock(instance, instance.last_inventory_update_time)
        return True

    def update_stock(self, instance, export_stock_from_date):
        """
        This method is used for export stock from Odoo to WooCommerce according to stock move.
        :param instance:
        :return:
        @author: Pragnadeep Pitroda @Emipro Technologies Pvt. Ltd on date 16-11-2019.
        :Task id: 156886
        """
        product_id_array = []
        product_obj = self.env['product.product']

        if not export_stock_from_date:
            export_stock_from_date = datetime.now() - timedelta(30)
        # get products which moved in between specific date duration.
        products = product_obj.get_products_based_on_movement_date(export_stock_from_date,
                                                                   instance.company_id)
        if products:
            product_id_array = sorted(list(map(lambda x: x['product_id'], products)))

        # This is used for get woo product template according to product id which is get from moves.
        woo_templates = self.env['woo.product.product.ept'].search(
            [('product_id', 'in', product_id_array),
             ('woo_is_manage_stock', '=', True)]).woo_template_id.filtered(
            lambda x: x.woo_instance_id == instance and x.exported_in_woo == True)
        if woo_templates:
            if instance.woo_version in ['v3', 'wc/v1']:
                self.with_context(
                    updated_products_in_inventory=product_id_array).update_stock_old_api(
                    instance,
                    woo_templates)
            else:
                self.with_context(
                    updated_products_in_inventory=product_id_array).update_stock_new_api(
                    instance, woo_templates)
        return True

    @api.model
    def get_gallery_images(self, instance, woo_template, template):
        tmpl_images = []
        position = 0
        gallery_img_keys = {}
        key = False
        gallery_images = woo_template.woo_image_ids.filtered(lambda x: not x.woo_variant_id)
        for br_gallery_image in gallery_images:
            image_id = br_gallery_image.woo_image_id
            img_url = ''
            if instance.woo_is_image_url:
                if br_gallery_image.response_url:
                    try:
                        img = requests.get(br_gallery_image.response_url, stream=True, verify=False,
                                           timeout=10)
                        if img.status_code == 200:
                            img_url = br_gallery_image.response_url
                        elif br_gallery_image.url:
                            img_url = br_gallery_image.url
                    except Exception:
                        img_url = br_gallery_image.url or ''
                elif br_gallery_image.url:
                    img_url = br_gallery_image.url
            else:
                if br_gallery_image.image and not image_id:
                    key = hashlib.md5(br_gallery_image.image).hexdigest()
                    if not key:
                        continue
                    if key in gallery_img_keys:
                        continue
                    else:
                        gallery_img_keys.update({key: br_gallery_image.id})
                    res = img_file_upload.upload_image(instance, br_gallery_image.image,
                                                       "%s_%s_%s" % (
                                                           template.name, template.categ_id.name,
                                                           template.id))
                    image_id = res and res.get('id', False) or ''
            if image_id:
                if instance.woo_is_image_url:
                    tmpl_images.append({'src': img_url, 'position': position})
                else:
                    tmpl_images.append({'id': image_id, 'position': position})
                position += 1
                br_gallery_image.woo_image_id = image_id
        return tmpl_images

    def woo_export_or_update_product_categories(self, wcapi, woo_template, instance, old,
                                                common_log_id, model_id):
        """
        :param wcapi: It is the object of connection with woo commerce rest api
        :param woo_template: It contain the browsable object of the woo product template
        :param instance: It contain the browsable object of the current instance
        :param old: It contain the api version of woo commerce and Its type is Boolean
        :param common_log_id: It contain the browsable object of the common log book ept
        :param model_id: It contain the id if the model class
        :return: It will return the list of tag ids
        @author: Dipak Gogiya @Emipro Technologies Pvt.Ltd
        """
        categ_ids = []
        common_log_line_obj = self.env['common.log.lines.ept']
        for woo_categ in woo_template.woo_categ_ids:
            if not woo_categ.woo_categ_id:
                woo_categ.sync_woo_product_category(instance, common_log_id,
                                                    woo_product_categ=woo_categ)
                woo_categ.woo_categ_id and categ_ids.append(woo_categ.woo_categ_id)
            else:
                categ_res = wcapi.get("products/categories/%s" % (woo_categ.woo_categ_id))
                if not isinstance(categ_res, requests.models.Response):
                    message = "Get Product Category \nResponse is not in proper format :: %s" % \
                              (categ_res)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    woo_template.product_tmpl_id)
                    continue
                try:
                    categ_res = categ_res.json()
                except Exception as e:
                    message = "Json Error : While import product category from WooCommerce for " \
                              "instance %s. \n%s" % (instance.name, e)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    woo_template.product_tmpl_id)
                    continue
                woo_product_category = categ_res.get('product_category') if old else categ_res
                if woo_product_category and woo_product_category.get('id'):
                    categ_ids.append(woo_categ.woo_categ_id)
                else:
                    if woo_template.exported_in_woo:
                        woo_categ.export_product_categs(instance, [woo_categ], common_log_id, model_id)
                    else:
                        woo_categ.sync_woo_product_category(instance, common_log_id,
                                                            woo_product_categ=woo_categ)
                    woo_categ.woo_categ_id and categ_ids.append(woo_categ.woo_categ_id)
        return categ_ids

    def woo_export_or_update_product_tags(self, wcapi, woo_template, instance, old, common_log_id,
                                          model_id):
        """
        :param wcapi: It is the object of connection with woo commerce rest api
        :param woo_template: It contain the browsable object of the woo product template
        :param instance: It contain the browsable object of the current instance
        :param old: It contain the api version of woo commerce and Its type is Boolean
        :param common_log_id: It contain the browsable object of the common log book ept
        :param model_id: It contain the id if the model class
        :return: It will return the list of tag ids
        @author: Dipak Gogiya @Emipro Technologies Pvt.Ltd
        """
        tag_ids = []
        common_log_line_obj = self.env['common.log.lines.ept']
        for woo_tag in woo_template.woo_tag_ids:
            if not woo_tag.woo_tag_id:
                woo_tag.woo_export_product_tags(instance, woo_tag, common_log_id, model_id)
                woo_tag.woo_tag_id and tag_ids.append(woo_tag.woo_tag_id)
            else:
                tag_res = wcapi.get("products/tags/%s" % (woo_tag.woo_tag_id))
                if not isinstance(tag_res, requests.models.Response):
                    message = "Get Product Tags \nResponse is not in proper format :: %s" % (
                        tag_res)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    woo_template.product_tmpl_id)
                    continue
                try:
                    tag_res = tag_res.json()
                except Exception as e:
                    message = "Json Error : While import product tag from WooCommerce for " \
                              "instance %s. \n%s" % (instance.name, e)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    woo_template.product_tmpl_id)
                    continue
                woo_product_tag = tag_res.get('product_tag') if old else tag_res
                if woo_product_tag and woo_product_tag.get('id'):
                    tag_ids.append(woo_tag.woo_tag_id)
                else:
                    woo_tag.woo_export_product_tags(instance, woo_tag, common_log_id, model_id)
                    woo_tag.woo_tag_id and tag_ids.append(woo_tag.woo_tag_id)
        return tag_ids

    def export_product_attributes_in_woo(self, instance, common_log_id, model_id, attribute):
        """
        This method is called when attribute type is select
        Find the existing product attribute if it is available then return It else create a new
        product attribute in woo commerce and get response and based on this response create
        that attribute and its value in the woo commerce connector of odoo and return arrribute id
        in Dict Format
        :param instance: It contain the browsable object of the current instance
        :param common_log_id: It contain the common log book id and its type is Object
        :param model_id: It contain the id of the model class
        :param attribute: It contain the product attribute
        :return: It will return the attribute id into Dict Format.
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        wcapi = instance.woo_connect()
        obj_woo_attribute = self.env['woo.product.attribute.ept']
        woo_attribute = obj_woo_attribute.search(
            [('attribute_id', '=', attribute.id), ('woo_instance_id', '=', instance.id),
             ('exported_in_woo', '=', True)], limit=1)
        if woo_attribute and woo_attribute.woo_attribute_id:
            return {attribute.id: woo_attribute.woo_attribute_id}
        attribute_data = {
            'name': attribute.name,
            'type': 'select',
        }
        if instance.woo_version == 'v3':
            attribute_data = {'product_attribute': attribute_data}
        attribute_res = wcapi.post("products/attributes", attribute_data)
        if not isinstance(attribute_res, requests.models.Response):
            message = "Export Product Attributes \nResponse is not in proper format :: %s" % (
                attribute_res)
            common_log_line_obj.woo_product_export_log_line(message, model_id, common_log_id, False)
            return False
        if attribute_res.status_code == 400:
            self.sync_woo_attribute(instance, common_log_id)
            woo_attribute = obj_woo_attribute.search(
                [('attribute_id', '=', attribute.id), ('woo_instance_id', '=', instance.id),
                 ('exported_in_woo', '=', True)], limit=1)
            if woo_attribute and woo_attribute.woo_attribute_id:
                return {attribute.id: woo_attribute.woo_attribute_id}
        if attribute_res.status_code not in [200, 201]:
            common_log_line_obj.woo_product_export_log_line(attribute_res.content, model_id,
                                                            common_log_id, False)
            return False
        attribute_response = attribute_res.json()
        if instance.woo_version == 'v3':
            attribute_response = attribute_response.get('product_attribute')
        woo_attribute_id = attribute_response.get('id')
        woo_attribute_name = attribute_response.get('name')
        woo_attribute_slug = attribute_response.get('slug')
        woo_attribute_order_by = attribute_response.get('order_by')
        has_archives = attribute_response.get('has_archives')
        obj_woo_attribute.create({
            'name': attribute and attribute.name or woo_attribute_name,
            'woo_attribute_id': woo_attribute_id,
            'order_by': woo_attribute_order_by,
            'slug': woo_attribute_slug, 'woo_instance_id': instance.id,
            'attribute_id': attribute.id,
            'exported_in_woo': True, 'has_archives': has_archives
        })
        return {attribute.id: woo_attribute_id}

    @api.model
    def get_product_attribute(self, template, instance, common_log_id, model_id):
        """
        :param template: It contain the browsable object of the product template
        :param instance: It contain the browsable object of the current instance
        :param common_log_id: It contain the common log book browsable object
        :param model_id: It contain the if of the model class and Its type Integer
        :return: It will return the attributes and Its type is List of Dictionary and return True
                or False for is_variable field
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        position = 0
        is_variable = False
        attributes = []
        for attribute_line in template.attribute_line_ids:
            options = []
            for option in attribute_line.value_ids:
                options.append(option.name)
            variation = False
            if attribute_line.attribute_id.create_variant in ['always', 'dynamic']:
                variation = True
            attribute_data = {
                'name': attribute_line.attribute_id.name,
                'slug': attribute_line.attribute_id.name.lower(),
                'position': position,
                'visible': True,
                'variation': variation,
                'options': options
            }
            if instance.woo_attribute_type == 'select':
                attrib_data = self.export_product_attributes_in_woo(instance, common_log_id,
                                                                    model_id,
                                                                    attribute_line.attribute_id)
                if not attrib_data:
                    break
                attribute_data.update({'id': attrib_data.get(attribute_line.attribute_id.id)})
            elif instance.woo_attribute_type == 'text':
                attribute_data.update({'name': attribute_line.attribute_id.name})
            position += 1
            if attribute_line.attribute_id.create_variant in ['always', 'dynamic']:
                is_variable = True
            attributes.append(attribute_data)
        return attributes, is_variable

    def prepare_product_variant_dict(self, instance, template, data, basic_detail, update_price,
                                     update_image, common_log_id, model_id):
        """
        This method is used for prepare the product variant dict based on parameters.
        Maulik : Updates variant in this method. Creates new variant, if not exported in woo.
                 Also updating the attributes in template for the new variant.
        :param instance: It contain the browsable object of the current instance.
        :param template: It contain the woo product template
        :param data: It contain the basic detail of woo product template and Its type is Dict
        :param basic_detail: It contain Either True or False and its type is Boolean
        :param update_price: It contain Either True or False and its type is Boolean
        :param update_image: It contain Either True or False and its type is Boolean
        :param common_log_id: It contain the log book id and its type is object
        :param model_id: It contain the id of the model class
        :return: It will return the updated data dictionary
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        common_log_line_obj = self.env['common.log.lines.ept']
        wcapi = instance.woo_connect()
        variants_to_create = []
        flag = True
        for variant in template.woo_product_ids:
            var_url = ''
            price = 0.0
            if variant.variant_id:
                info = {'id': variant.variant_id}
                if basic_detail:
                    weight = self.convert_weight_by_uom(variant.product_id.weight, instance)
                    info.update({'sku': variant.default_code, 'weight': str(weight),
                                 "manage_stock":variant.woo_is_manage_stock})
                if update_image:
                    info.update(self.get_variant_image(instance, variant))
            else:
                attributes = self.get_product_attribute(template.product_tmpl_id, instance, common_log_id,
                                                        model_id)[0]
                info = self.get_variant_data(variant, instance, False)

            if update_price:
                price = instance.woo_pricelist_id.get_product_price(variant.product_id, 1.0,
                                                                    partner=False,
                                                                    uom_id=variant.product_id.uom_id.id)
                info.update({'regular_price': str(price), 'sale_price': str(price)})

            if template.woo_tmpl_id != variant.variant_id:
                if variant.variant_id:
                    data.get('variations').append(info)
                else:
                    variants_to_create.append(info)
                flag = True
            elif template.woo_tmpl_id == variant.variant_id:
                del data['variations']
                if basic_detail:
                    data.update({'sku': variant.default_code, "manage_stock":variant.woo_is_manage_stock})
                    if var_url:
                        if instance.woo_is_image_url:
                            if data.get('images'):
                                data.get('images').insert(0, {'src': var_url, 'position': 0})
                            else:
                                data.update({'images': [{'src': var_url, 'position': 0}]})
                        else:
                            if data.get('images'):
                                data.get('images').insert(0, {'id': var_url, 'position': 0})
                            else:
                                data.update({'images': [{'id': var_url, 'position': 0}]})
                if update_price:
                    data.update({'regular_price': str(price), 'sale_price': str(price)})
                flag = True

        if instance.woo_version in ['wc/v2', 'wc/v3'] and data.get('variations'):
            variant_batches = self.prepare_batches(data.get('variations'))
            for woo_variants in variant_batches:
                _logger.info('variations batch processing')
                res = wcapi.post('products/%s/variations/batch' % (data.get('id')),
                                 {'update': woo_variants})
                _logger.info('variations batch process completed [status: %s]', res.status_code)
                if res.status_code in [200, 201]:
                    del data['variations']
                if res.status_code not in [200, 201]:
                    message = "Update Product Variations\n%s" % (res.content)
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
        if variants_to_create:
            """Needed to update the attributes of template for adding new variant, while update
            process."""
            _logger.info("Updating attributes of %s in Woo.." % (template.name))
            if data.get("variations"):
                del data['variations']
            data.update({"attributes": attributes})
            res = wcapi.put("products/%s" % (data.get("id")), data)

            _logger.info("Creating variants in Woo..")
            res = wcapi.post('products/%s/variations/batch' % (data.get('id')),
                             {'create': variants_to_create})
            try:
                response = res.json()
            except Exception as e:
                message = "Json Error : While update products to WooCommerce for instance %s." \
                          " \n%s" % (instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id,
                                                                False)
                return data, flag
            for product in response.get("create"):
                if product.get("error"):
                    message = "Update Product \n%s" % (product.get("error").get('message'))
                    common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                    common_log_id,
                                                                    False)
                else:
                    variant_id = product.get("id")
                    sku = product.get("sku")
                    variant = template.woo_product_ids.filtered(lambda x:x.default_code == sku)
                    if variant:
                        variant.write({"variant_id":variant_id, "exported_in_woo":True})
            self.sync_woo_attribute_term(instance, common_log_id)
        return data, flag

    def get_product_update_data(self, wcapi, template, instance, update_image,
                                update_basic_detail, data, common_log_id, model_id):
        """
         This method is used for prepare the products details into Dictionary based on parameters
        :param wcapi: It contain the connection object between odoo and woo
        :param template: It contain the woo product template
        :param instance: It contain the browsable object of the current instance
        :param update_image: It contain Either True or False and its type is Boolean
        :param update_basic_detail: It contain Either True or False and its type is Boolean
        :param data: It contain the basic detail of woo product template and Its type is Dict
        :param common_log_id: It contain the common log book id and its type is Object
        :param model_id: It contain the id of the model class
        :return: It will return the updated product dictionary
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        old = True if instance.woo_version == "v3" else False
        flag = False
        tmpl_images = []
        if update_image:
            tmpl_images += self.get_gallery_images(instance, template, template.product_tmpl_id)
            data.update({"images": tmpl_images})
            flag = True

        if update_basic_detail:
            categ_ids = []
            tag_ids = []

            weight = self.convert_weight_by_uom(template.product_tmpl_id.weight, instance)

            if instance.woo_version != 'v3':
                description = ''
                short_description = ''
                if template.woo_description:
                    woo_template_id = template.with_context(lang=instance.woo_lang_id.code)
                    description = woo_template_id.woo_description

                if template.woo_short_description:
                    woo_template_id = template.with_context(lang=instance.woo_lang_id.code)
                    short_description = woo_template_id.woo_short_description
                data.update({
                    'name': template.name,
                    'enable_html_description': True,
                    'enable_html_short_description': True, 'description': description,
                    'short_description': short_description,
                    'weight': str(weight),
                    'taxable': template.taxable and 'true' or 'false'
                })
            else:
                data.update({
                    'enable_html_description': True,
                    'enable_html_short_description': True,
                    'type': 'simple',
                    'title': template.name,
                    'description': template.woo_description,
                    'weight': str(weight),
                    'short_description': template.woo_short_description,
                    'taxable': template.taxable and 'true' or 'false',
                    'shipping_required': 'true'
                })

            categ_ids += self.woo_export_or_update_product_categories(wcapi, template, instance,
                                                                      old, common_log_id, model_id)

            if categ_ids:
                categ_ids = list(set(categ_ids))
                if not old:
                    categ_ids = [{'id': cat_id} for cat_id in categ_ids]
                data.update({'categories': categ_ids})

            tag_ids += self.woo_export_or_update_product_tags(wcapi, template, instance, old,
                                                              common_log_id, model_id)

            if tag_ids:
                tag_ids = list(set(tag_ids))
                if not old:
                    tag_ids = [{'id': tag_id} for tag_id in tag_ids]
                data.update({'tags': tag_ids})

        return flag, data

    @api.model
    def export_products_in_woo(self, instance, woo_templates, update_price, publish, update_image,
                               basic_detail, common_log_id):
        """
        :param instance: It contain the browesable object of the current instance
        :param woo_templates: It contain the browsable object of the woo product templates
        :param update_price: It contain either True or False and its type is Boolean
        :param publish: It contain either True or False and its type is Boolean
        :param update_image: It contain either True or False and its type is Boolean
        :param basic_detail: It contain either True or False and its type is Boolean
        :param common_log_id: It contain the browsable object of common log book ept model
        :return: It will return the True if the process is successfully complete
         @author: Dipak Gogiya @Emipro Technologies Pvt.Ltd
        """
        wcapi = instance.woo_connect()
        # common_product_image_obj = self.env['common.product.image.ept']
        woo_product_product_ept = self.env['woo.product.product.ept']
        common_log_line_obj = self.env['common.log.lines.ept']
        model_id = common_log_line_obj.get_model_id('woo.product.template.ept')
        variants = []
        for woo_template in woo_templates:
            template = woo_template.product_tmpl_id
            data = self.get_product_data(wcapi, instance, woo_template, publish, update_price,
                                         update_image, basic_detail, template, common_log_id,
                                         model_id)
            if instance.woo_version == 'wc/v2' or instance.woo_version == 'wc/v3':  # instance.woo_version != 'v3'
                variants = data.get('variations') or []
                variants and data.update({'variations': []})
            if instance.woo_version == 'v3':
                new_product = wcapi.post('products', {'product': data})
            else:
                new_product = wcapi.post('products', data)
            if not isinstance(new_product, requests.models.Response):
                message = "Export Product\nResponse is not in proper format :: %s" % (
                    new_product)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id,
                                                                woo_template.product_tmpl_id)
                continue
            if new_product.status_code not in [200, 201]:
                common_log_line_obj.woo_product_export_log_line(new_product.content, model_id,
                                                                common_log_id,
                                                                woo_template.product_tmpl_id)
                continue
            try:
                response = new_product.json()
            except Exception as e:
                message = "Json Error : While export product to WooCommerce for instance %s. \n%s" % (
                    instance.name, e)
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id,
                                                                woo_template.product_tmpl_id)
                continue
            if response.get('data', {}) and response.get('data', {}).get('status') not in [200,
                                                                                           201]:
                message = response.get('message')
                if response.get('code') == 'woocommerce_rest_product_sku_already_exists':
                    message = "%s, ==> %s" % (message, data.get('name'))
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id,
                                                                woo_template.product_tmpl_id)
                continue
            if not isinstance(response, dict):
                message = "Export Product, Response is not in proper format"
                common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                common_log_id,
                                                                woo_template.product_tmpl_id)
                continue
            response_variations = []
            if instance.woo_version == 'wc/v1':  # instance.woo_version == 'v3'
                response_variations = response.get('variations')
            if instance.woo_version == 'v3':
                response_variations = response.get('product').get('variations')
            woo_tmpl_id = response.get('id') if not instance.woo_version == 'v3' else response.get(
                'product').get('id') or False

            if woo_tmpl_id and instance.woo_version != 'wc/v1' and variants:
                response_variations = []
                vairant_batches = []
                start, end = 0, 100
                if len(variants) > 100:
                    while True:
                        w_products_ids = variants[start:end]
                        if not w_products_ids:
                            break
                        temp = end + 100
                        start, end = end, temp
                        if w_products_ids:
                            vairant_batches.append(w_products_ids)
                else:
                    vairant_batches.append(variants)
                for woo_variants in vairant_batches:
                    for variant in woo_variants:
                        if variant.get('image'):
                            variant.update({'image': variant.get('image')})
                    variant_response = wcapi.post("products/%s/variations/batch" % (woo_tmpl_id),
                                                  {'create': woo_variants})
                    if variant_response.status_code not in [200, 201]:
                        common_log_line_obj.woo_product_export_log_line(variant_response.content,
                                                                        model_id, common_log_id,
                                                                        woo_template.product_tmpl_id)
                        continue
                    try:
                        response_variations += variant_response.json().get('create')
                    except Exception as e:
                        message = "Json Error : While retrive product response from WooCommerce " \
                                  "for instance %s. \n%s" % (instance.name, e)
                        common_log_line_obj.woo_product_export_log_line(message, model_id,
                                                                        common_log_id,
                                                                        woo_template.product_tmpl_id)
                        continue

            for response_variation in response_variations:
                if response_variation.get('error'):
                    common_log_line_obj.woo_product_export_log_line(response_variation.get('error'),
                                                                    model_id, common_log_id,
                                                                    woo_template.product_tmpl_id)
                    continue
                response_variant_data = {}
                variant_sku = response_variation.get('sku')
                variant_id = response_variation.get('id')
                if instance.woo_is_image_url:
                    variant_image = response_variation.get('image')
                    variant_image_id = variant_image and variant_image.get('id') or False
                    variant_image_url = variant_image and variant_image.get('src') or ''
                    response_variant_data.update(
                        {'woo_image_id': variant_image_id, 'response_url': variant_image_url})
                if instance.woo_version == 'v3':
                    variant_created_at = response_variation.get('created_at').replace('T',
                                                                                      ' ').replace(
                        'Z', '')
                    variant_updated_at = response_variation.get('updated_at').replace('T',
                                                                                      ' ').replace(
                        'Z', '')
                else:
                    variant_created_at = response_variation.get('date_created').replace('T', ' ')
                    variant_updated_at = response_variation.get('date_modified').replace('T', ' ')
                woo_product = woo_product_product_ept.search(
                    [('default_code', '=', variant_sku),
                     ('woo_template_id', '=', woo_template.id),
                     ('woo_instance_id', '=', instance.id)])
                response_variant_data.update(
                    {
                        'variant_id': variant_id, 'created_at': variant_created_at,
                        'updated_at': variant_updated_at, 'exported_in_woo': True
                    })
                woo_product and woo_product.write(response_variant_data)
            total_variants_in_woo = 0
            if instance.woo_version == 'v3':
                created_at = response.get('product').get('created_at').replace('T', ' ').replace(
                    'Z', '')
                updated_at = response.get('product').get('updated_at').replace('T', ' ').replace(
                    'Z', '')
                if not template.attribute_line_ids:
                    woo_product = woo_template.woo_product_ids
                    woo_product.write(
                        {
                            'variant_id': woo_tmpl_id, 'created_at': created_at,
                            'updated_at': updated_at,
                            'exported_in_woo': True
                        })
                total_variants_in_woo = len(response_variations) if response_variations else 1
            else:
                created_at = response.get('date_created').replace('T', ' ')
                updated_at = response.get('date_modified').replace('T', ' ')

                if template.product_variant_count == 1 and not template.attribute_line_ids:
                    woo_product = woo_template.woo_product_ids
                    woo_product.write({
                        'variant_id': woo_tmpl_id,
                        'created_at': created_at or False,
                        'updated_at': updated_at or False, 'exported_in_woo': True
                    })
                total_variants_in_woo = response.get('variations') and len(
                    response.get('variations')) or 1

            tmpl_data = {
                'woo_tmpl_id': woo_tmpl_id, 'created_at': created_at or False,
                'updated_at': updated_at or False, 'exported_in_woo': True,
                'total_variants_in_woo': total_variants_in_woo
            }
            tmpl_data.update(
                {'website_published': True}) if publish == 'publish' else tmpl_data.update(
                {'website_published': False})
            woo_template.write(tmpl_data)
            self.sync_woo_attribute_term(instance, common_log_id)
            self._cr.commit()
        return True

    def get_product_data(self, wcapi, instance, woo_template, publish, update_price,
                         update_image, basic_detail, template, common_log_id, model_id):
        """
        :param wcapi: It contain the connection object of the woo rest api based on api version
        :param instance: It contain the browsable object of the Instance
        :param woo_template: It contain the browsable object of the product template
        :param publish: It contain either True or False and its type is Boolean
        :param update_price: It contain either True or False and its type is Boolean
        :param update_image: It contain either True or False and its type is Boolean
        :param basic_detail: It contain the basic details such as category, product description,
                            tags etc If Its value is True and Its type is Boolean
        :param template: It contain the browsable object of the product template
        :param common_log_id: It contain the browsable object of the common log book
        :param model_id: It contain the id of the model class and Its type is Integer
        :return: It will Return the updated data based on conditions and Its type is Dictionary
         @author: Dipak Gogiya @Emipro Technologies Pvt.Ltd
        """
        old = True if instance.woo_version == "v3" else False
        data = {}
        if basic_detail:
            categ_ids = []
            tag_ids = []
            description = ''
            short_description = ''
            if woo_template.woo_description:
                woo_template_id = woo_template.with_context(lang=instance.woo_lang_id.code)
                description = woo_template_id.woo_description

            if woo_template.woo_short_description:
                woo_template_id = woo_template.with_context(lang=instance.woo_lang_id.code)
                short_description = woo_template_id.woo_short_description

            weight = self.convert_weight_by_uom(template.weight, instance)

            data = {
                'enable_html_description': True, 'enable_html_short_description': True,
                'type': 'simple', 'title' if old else 'name': woo_template.name,
                'description': description, 'weight': str(weight),
                'short_description': short_description,
                'taxable': woo_template.taxable and 'true' or 'false',
                'shipping_required': 'true'
            }

            categ_ids += self.woo_export_or_update_product_categories(wcapi, woo_template, instance,
                                                                      old, common_log_id, model_id)
            if categ_ids:
                categ_ids = list(set(categ_ids))
                if not old:
                    categ_ids = [{'id': cat_id} for cat_id in categ_ids]
                data.update({'categories': categ_ids})

            tag_ids += self.woo_export_or_update_product_tags(wcapi, woo_template, instance, old,
                                                              common_log_id, model_id)

            if tag_ids:
                tag_ids = list(set(tag_ids))
                if not old:
                    tag_ids = [{'id': tag_id} for tag_id in tag_ids]
                data.update({'tags': tag_ids})

            attributes, is_variable = self.get_product_attribute(template, instance, common_log_id,
                                                                 model_id)
            if is_variable:
                data.update({'type': 'variable'})

            if template.attribute_line_ids:
                variations = []
                for variant in woo_template.woo_product_ids:
                    variation_data = {}
                    product_variant = self.get_variant_data(variant, instance, update_image)
                    variation_data.update(product_variant)
                    if update_price:
                        if data.get('type') == 'simple':
                            data.update(self.get_product_price(instance, variant))
                        else:
                            variation_data.update(self.get_product_price(instance, variant))
                    variations.append(variation_data)
                default_att = variations and variations[0].get('attributes') or []
                data.update({
                    'attributes': attributes, 'default_attributes': default_att,
                    'variations': variations
                })
                if data.get('type') == 'simple':
                    data.update({'sku': str(variant.default_code),
                                 "manage_stock":variant.woo_is_manage_stock})
            else:
                variant = woo_template.woo_product_ids
                data.update(self.get_variant_data(variant, instance, update_image))
                if update_price:
                    data.update(self.get_product_price(instance, variant))

        if publish == 'publish':
            data.update({'status': 'publish'})
        else:
            data.update({'status': 'draft'})

        if update_image:
            tmpl_images = []
            tmpl_images += self.get_gallery_images(instance, woo_template, template)
            tmpl_images and data.update({"images": tmpl_images})
        return data

    def convert_weight_by_uom(self, weight, instance, import_process=False):
        """
        This method converts weight from Odoo's weight uom to Woo's uom.
        @author: Maulik Barad on Date 24-Jun-2020.
        @param weight: Weight in float.
        @param instance: Instance of Woo.
        @param import_process: In which process, we are converting the weight import or export.
        """
        woo_weight_uom = instance.weight_uom_id
        product_weight_uom = self.env.ref("uom.product_uom_lb") if self.env["ir.config_parameter"].sudo().get_param("product.weight_in_lbs") == '1' else self.env.ref("uom.product_uom_kgm")

        if woo_weight_uom != product_weight_uom:
            if import_process:
                weight = woo_weight_uom._compute_quantity(weight, product_weight_uom)
            else:
                weight = product_weight_uom._compute_quantity(weight, woo_weight_uom)
        return weight


class ProductProductEpt(models.Model):
    _name = "woo.product.product.ept"
    _order = 'product_id'
    _description = "WooCommerce Product"

    product_url = fields.Text("Product URL")
    name = fields.Char("Title")
    woo_instance_id = fields.Many2one("woo.instance.ept", "Instance", required=1)
    default_code = fields.Char("Default Code")
    product_id = fields.Many2one("product.product", "Product", required=1, ondelete="cascade")
    woo_template_id = fields.Many2one("woo.product.template.ept", "Woo Template", required=1,
                                      ondelete="cascade")
    active = fields.Boolean('Active', default=True)
    exported_in_woo = fields.Boolean("Exported In Woo")
    variant_id = fields.Char("Variant Id")
    fix_stock_type = fields.Selection([('fix', 'Fix'), ('percentage', 'Percentage')],
                                      string='Fix Stock Type')
    fix_stock_value = fields.Float(string='Fix Stock Value', digits="Product UoS")
    created_at = fields.Datetime("Created At")
    updated_at = fields.Datetime("Updated At")
    woo_is_image_url = fields.Boolean("Is Image Url ?", related="woo_instance_id.woo_is_image_url")
    woo_is_manage_stock = fields.Boolean("Is Manage Stock?",
                                         help="Enable stock management at product level in WooCommerce",
                                         default=True)
    woo_image_ids = fields.One2many("woo.product.image.ept", "woo_variant_id")

    def toggle_active(self):
        """
        Archiving related woo product template if there is only one active woo product
        :parameter: self
        :return: res
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 09/12/2019.
        :Task id: 158502
        """
        with_one_active = self.filtered(
            lambda product: len(product.woo_template_id.woo_product_ids) == 1)
        for product in with_one_active:
            product.woo_template_id.toggle_active()
        return super(ProductProductEpt, self - with_one_active).toggle_active()
