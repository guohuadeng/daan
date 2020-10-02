import base64
import csv
import logging

from csv import DictWriter
from datetime import datetime
from io import StringIO, BytesIO

from odoo import models, fields, _
from odoo.exceptions import ValidationError, Warning
from _collections import OrderedDict

_logger = logging.getLogger("Woo")


class PrepareProductForExport(models.TransientModel):
    """
    Model for adding Odoo products into Woo Layer.
    @author: Haresh Mori on Date 13-Apr-2020.
    """
    _name = "woo.prepare.product.for.export.ept"
    _description = "Prepare product for export in Woocommerce"

    export_method = fields.Selection([("csv", "Export in CSV file"),
                                      ("direct", "Export in Woo Layer")], default="csv")
    woo_instance_id = fields.Many2one("woo.instance.ept")
    datas = fields.Binary("File")
    choose_file = fields.Binary(filters="*.csv", help="Select CSV file to upload.")
    file_name = fields.Char(string="File Name", help="Name of CSV file.")
    csv_data = fields.Binary('CSV File', readonly=True, attachment=False)
    filename = fields.Char(string='Filename', size=256, readonly=True)

    def prepare_product_for_export(self):
        """
        This method is used to export products in Woo layer as per selection.
        If "direct" is selected, then it will direct export product into Woo layer.
        If "csv" is selected, then it will export product data in CSV file, if user want to do some
        modification in name, description, etc. before importing into Woocommmerce.
        """
        _logger.info("Starting product exporting via %s method..." % self.export_method)

        active_template_ids = self._context.get("active_ids", [])
        templates = self.env["product.template"].browse(active_template_ids)
        product_templates = templates.filtered(lambda template: template.type == "product")
        if not product_templates:
            raise Warning(_("It seems like selected products are not Storable products."))

        if self.export_method == "direct":
            return self.export_direct_in_woo(product_templates)
        elif self.export_method == "csv":
            return self.export_csv_file(product_templates)

    def export_direct_in_woo(self, product_templates):
        """
        Creates new product or updates existing product in Woo layer.
        @author: Haresh Mori on Date 14-Apr-2020.
        """
        woo_template_id = False
        woo_template_obj = self.env["woo.product.template.ept"]
        woo_product_obj = self.env["woo.product.product.ept"]
        woo_product_image_obj = self.env["woo.product.image.ept"]
        woo_category_dict = {}

        variants = product_templates.product_variant_ids
        woo_instance = self.woo_instance_id

        for variant in variants:
            if not variant.default_code:
                continue
            product_template = variant.product_tmpl_id
            if product_template.attribute_line_ids and len(
                    product_template.attribute_line_ids.filtered(
                        lambda x: x.attribute_id.create_variant == "always")) > 0:
                product_type = 'variable'
            else:
                product_type = 'simple'
            woo_template = woo_template_obj.search([
                ("woo_instance_id", "=", woo_instance.id),
                ("product_tmpl_id", "=", product_template.id)])

            woo_product_template_vals = (
                {
                    'product_tmpl_id': product_template.id,
                    'woo_instance_id': woo_instance.id,
                    'name': product_template.name,
                    'woo_product_type': product_type
                })

            if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                woo_product_template_vals.update({"woo_description": product_template.description_sale,
                                                  "woo_short_description": product_template.description})

            if product_template.categ_id:
                woo_category_dict = self.create_categ_in_woo(product_template.categ_id, woo_instance.id,
                                                             woo_category_dict)  # create category
                woo_categ_id = self.update_category_info(product_template.categ_id, woo_instance.id)
                woo_categ_ids = [(6, 0, woo_categ_id.ids)]
                woo_product_template_vals.update({'woo_categ_ids': woo_categ_ids})

            if not woo_template:
                woo_template = woo_template_obj.create(woo_product_template_vals)
                woo_template_id = woo_template.id
            else:
                if woo_template_id != woo_template.id:
                    woo_template.write(woo_product_template_vals)
                    woo_template_id = woo_template.id

            # For adding all odoo images into Woo layer.
            woo_product_image_list = []
            product_template = woo_template.product_tmpl_id
            for odoo_image in product_template.ept_image_ids.filtered(lambda x: not x.product_id):
                woo_product_image = woo_product_image_obj.search_read(
                    [("woo_template_id", "=", woo_template_id),
                     ("odoo_image_id", "=", odoo_image.id)], ["id"])
                if not woo_product_image:
                    woo_product_image_list.append({
                        "odoo_image_id": odoo_image.id,
                        "woo_template_id": woo_template_id
                    })
            if woo_product_image_list:
                woo_product_image_obj.create(woo_product_image_list)

            woo_variant = woo_product_obj.search(
                [('woo_instance_id', '=', woo_instance.id), (
                    'product_id', '=', variant.id),
                 ('woo_template_id', '=', woo_template.id)])
            woo_variant_vals = ({
                'woo_instance_id': woo_instance.id,
                'product_id': variant.id,
                'woo_template_id': woo_template.id,
                'default_code': variant.default_code,
                'name': variant.name,
            })
            if not woo_variant:
                woo_variant = woo_product_obj.create(woo_variant_vals)
            else:
                woo_variant.write(woo_variant_vals)

            # For adding all odoo images into Woo layer.
            product_id = woo_variant.product_id
            odoo_image = product_id.ept_image_ids
            if odoo_image:
                woo_product_image = woo_product_image_obj.search_read(
                    [("woo_template_id", "=", woo_template_id),
                     ("woo_variant_id", "=", woo_variant.id),
                     ("odoo_image_id", "=", odoo_image[0].id)], ["id"])
                if not woo_product_image:
                    woo_product_image_obj.create({
                        "odoo_image_id": odoo_image[0].id,
                        "woo_variant_id": woo_variant.id,
                        "woo_template_id": woo_template_id,
                    })

            # pricelist_item = self.env['product.pricelist.item'].search(
            #     [('pricelist_id', '=', woo_instance.woo_pricelist_id.id),
            #      ('product_id', '=', variant.id)], limit=1)
            #
            # price = woo_variant.product_id.lst_price
            # if not pricelist_item:
            #     woo_instance.woo_pricelist_id.write({
            #         'item_ids': [(0, 0, {
            #             'applied_on': '0_product_variant',
            #             'product_id': variant.id,
            #             'compute_price': 'fixed',
            #             'fixed_price': price
            #         })]
            #     })
            # else:
            #     if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
            #         instance_currency = pricelist_item.currency_id
            #         product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
            #         price = instance_currency.compute(float(woo_variant.product_id.lst_price),
            #                                           product_company_currency)
            #     pricelist_item.write({'fixed_price': price})
        return True

    def export_csv_file(self, odoo_template_ids):
        """
        This method is used for export the odoo products in csv file format
        :param self: It contain the current class Instance
        :return: It will return the CSV File if the Export process successfully complete
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd.
        """
        buffer = StringIO()
        delimiter = ','
        field_names = ['template_name', 'product_name', 'product_default_code',
                       'woo_product_default_code', 'product_description', 'sale_description',
                       'PRODUCT_TEMPLATE_ID', 'PRODUCT_ID', 'CATEGORY_ID']
        csv_writer = DictWriter(buffer, field_names, delimiter=delimiter)
        csv_writer.writer.writerow(field_names)
        rows = []
        for odoo_template in odoo_template_ids:
            if len(odoo_template.product_variant_ids.ids) == 1 and not odoo_template.default_code:
                continue
            position = 0
            for product in odoo_template.product_variant_ids.filtered(
                    lambda variant: variant.default_code != False):
                row = {
                    'template_name': odoo_template.name,
                    'product_name': product.name,
                    'product_default_code': product.default_code,
                    'woo_product_default_code': product.default_code,
                    'product_description': product.description or '' if position == 0 else '',
                    'sale_description': product.description_sale or '' if position == 0 else '',
                    'PRODUCT_TEMPLATE_ID': odoo_template.id,
                    'PRODUCT_ID': product.id,
                    'CATEGORY_ID': odoo_template.categ_id.id or '' if position == 0 else '',
                }
                rows.append(row)
                # csv_writer.writerow(row)
                position = 1
        if not rows:
            raise Warning(_('No data found to be exported.\n\nPossible Reasons:\n   - SKU(s) are not set properly.'))
        csv_writer.writerows(rows)
        buffer.seek(0)
        file_data = buffer.read().encode()
        self.write({
            'csv_data': base64.encodestring(file_data),
            'file_name': 'export_product',
        })

        return {
            'name': 'CSV',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=woo.prepare.product.for.export.ept&id=" + str(
                self.id) + "&filename_field=filename&field=csv_data&download=true&filename=%s.csv" % (
                           self.file_name + str(datetime.now().strftime("%d/%m/%Y:%H:%M:%S"))),
            'target': 'self',
        }

    def import_products_from_csv(self):
        """
        This method used to import product using csv file in Woo
        @param : self : It contain the current class instance
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        :return: It will return the True the process is completed.
        """
        woo_product_template = self.env['woo.product.template.ept']
        woo_product_obj = self.env['woo.product.product.ept']
        woo_common_log_obj = self.env["common.log.book.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        product_tmpl_obj = self.env['product.template']
        category_obj = self.env['product.category']
        woo_product_image_obj = self.env['woo.product.image.ept']
        instance_id = self.woo_instance_id
        woo_category_dict = {}
        if not self.choose_file:
            raise Warning(_('Please Select The file for Start process The Product Sync'))
        if self.file_name and not self.file_name.lower().endswith('.csv'):
            raise Warning(_("Please provide only CSV File to Import Products"))

        file_data = self.read_file()
        woo_common_log_id = woo_common_log_obj.create(
            {
                'type': 'import',
                'module': 'woocommerce_ept',
                'woo_instance_id': instance_id.id,
                'active': True,
            })

        required_field = ['template_name', 'product_name', 'product_default_code',
                          'woo_product_default_code', 'product_description', 'sale_description',
                          'PRODUCT_TEMPLATE_ID', 'PRODUCT_ID', 'CATEGORY_ID']
        for required_field in required_field:
            if not required_field in file_data.fieldnames:
                raise Warning(
                    _("Required Column %s Is Not Available In CSV File") % (required_field))

        row_no = 0
        model_id = common_log_line_obj.get_model_id("woo.process.import.export")
        woo_template_id = False

        for record in file_data:
            woo_categ_ids = [(6, 0, [])]
            if not record['PRODUCT_TEMPLATE_ID'] or not record['PRODUCT_ID']:
                message = ""
                if not record['PRODUCT_TEMPLATE_ID']:
                    if message:
                        message += ', '
                    message += 'Product Template Id not available in Row Number %s' % (row_no)
                if not record['PRODUCT_ID']:
                    if message:
                        message += ', '
                    message += 'Product Id not available in Row Number %s' % (row_no)
                vals = {
                    'message': message,
                    'model_id': model_id,
                    'log_line_id': woo_common_log_id.id,
                    'woo_instance_id': instance_id.id
                }
                common_log_line_obj.create(vals)
                row_no += 1
                continue

            woo_template = woo_product_template.search(
                [('woo_instance_id', '=', instance_id.id),
                 ('product_tmpl_id', '=', int(record['PRODUCT_TEMPLATE_ID']))])
            product_template = product_tmpl_obj.browse(int(record['PRODUCT_TEMPLATE_ID']))
            if product_template.attribute_line_ids and len(
                    product_template.attribute_line_ids.filtered(
                        lambda x: x.attribute_id.create_variant == "always")) > 0:
                product_type = 'variable'
            else:
                product_type = 'simple'
            categ_obj = category_obj.browse(int(record.get('CATEGORY_ID'))) if record.get(
                'CATEGORY_ID') else ''
            woo_product_template_vals = {
                'product_tmpl_id': int(record['PRODUCT_TEMPLATE_ID']),
                'woo_instance_id': instance_id.id,
                'name': record['template_name'],
                'woo_product_type': product_type
            }

            if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                woo_product_template_vals.update({'woo_description': record.get('sale_description'),
                                                  'woo_short_description': record.get('product_description')})

            if not woo_template:
                if categ_obj:
                    woo_category_dict = self.create_categ_in_woo(categ_obj, instance_id.id,
                                                                 woo_category_dict)  # create category
                    woo_categ_id = self.update_category_info(categ_obj, instance_id.id)
                    woo_categ_ids = [(6, 0, woo_categ_id.ids)]
                    woo_product_template_vals.update({'woo_categ_ids': woo_categ_ids})

                woo_template = woo_product_template.create(woo_product_template_vals)
                woo_template_id = woo_template.id
            else:
                if woo_template_id != woo_template.id:
                    woo_category_dict = self.create_categ_in_woo(categ_obj, instance_id.id,
                                                                 woo_category_dict)  # create category
                    if categ_obj:
                        woo_categ_id = self.update_category_info(categ_obj, instance_id.id)
                        woo_product_template_vals.update({'woo_categ_ids': woo_categ_ids})

                    woo_template.write(woo_product_template_vals)
                    woo_template_id = woo_template.id

            # For adding all odoo images into Woo layer.
            woo_product_image_list = []
            product_template = woo_template.product_tmpl_id
            for odoo_image in product_template.ept_image_ids.filtered(lambda x: not x.product_id):
                woo_product_image = woo_product_image_obj.search_read(
                    [("woo_template_id", "=", woo_template_id),
                     ("odoo_image_id", "=", odoo_image.id)], ["id"])
                if not woo_product_image:
                    woo_product_image_list.append({
                        "odoo_image_id": odoo_image.id,
                        "woo_template_id": woo_template_id
                    })
            if woo_product_image_list:
                woo_product_image_obj.create(woo_product_image_list)

            woo_variant = woo_product_obj.search(
                [('woo_instance_id', '=', instance_id.id), (
                    'product_id', '=', int(record['PRODUCT_ID'])),
                 ('woo_template_id', '=', woo_template.id)])
            if not woo_variant:
                woo_variant_vals = ({
                    'woo_instance_id': instance_id.id,
                    'product_id': int(record['PRODUCT_ID']),
                    'woo_template_id': woo_template.id,
                    'default_code': record['woo_product_default_code'],
                    'name': record['product_name'],
                })
                woo_variant = woo_product_obj.create(woo_variant_vals)
            else:
                woo_variant_vals = ({
                    'woo_instance_id': instance_id.id,
                    'product_id': int(record['PRODUCT_ID']),
                    'woo_template_id': woo_template.id,
                    'default_code': record['woo_product_default_code'],
                    'name': record['product_name'],
                })
                woo_variant.write(woo_variant_vals)

            # For adding all odoo images into Woo layer.
            product_id = woo_variant.product_id
            odoo_image = product_id.ept_image_ids
            if odoo_image:
                woo_product_image = woo_product_image_obj.search_read(
                    [("woo_template_id", "=", woo_template_id),
                     ("woo_variant_id", "=", woo_variant.id),
                     ("odoo_image_id", "=", odoo_image[0].id)], ["id"])
                if not woo_product_image:
                    woo_product_image_obj.create({
                        "odoo_image_id": odoo_image[0].id,
                        "woo_variant_id": woo_variant.id,
                        "woo_template_id": woo_template_id,
                    })

            # pricelist_item = self.env['product.pricelist.item'].search(
            #     [('pricelist_id', '=', instance_id.woo_pricelist_id.id),
            #      ('product_id', '=', int(record['PRODUCT_ID']))], limit=1)
            #
            # price = woo_variant.product_id.lst_price
            # if not pricelist_item:
            #     instance_id.woo_pricelist_id.write({
            #         'item_ids': [(0, 0, {
            #             'applied_on': '0_product_variant',
            #             'product_id': int(record['PRODUCT_ID']),
            #             'compute_price': 'fixed',
            #             'fixed_price': price
            #         })]
            #     })
            # else:
            #     if pricelist_item.currency_id.id != woo_template.product_tmpl_id.company_id.currency_id.id:
            #         instance_currency = pricelist_item.currency_id
            #         product_company_currency = woo_template.product_tmpl_id.company_id.currency_id
            #         price = instance_currency.compute(float(woo_variant.product_id.lst_price),
            #                                           product_company_currency)
            #     pricelist_item.write({'fixed_price': price})
            row_no += 1
        if not woo_common_log_id.log_lines:
            woo_common_log_id.sudo().unlink()
        return True

    def read_file(self):
        """
            Read selected .csv file based on delimiter
            @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
            :return: It will return the object of csv file data
        """
        self.write({'csv_data': self.choose_file})
        self._cr.commit()
        import_file = BytesIO(base64.decodestring(self.csv_data))
        file_read = StringIO(import_file.read().decode())
        reader = csv.DictReader(file_read, delimiter=',')
        return reader

    def create_categ_in_woo(self, category_id, instance, woo_category_dict, ctg_list=[]):
        """
        This method is used for find the parent category and its sub category based on category id and
        create or update the category in woo second layer of woo category model
        :param categ_id: It contain the product category and its type is object
        :param instance: It contain the browsable object of the current instance
        :param ctg_list: It contain the category ids list
        :return: It will return True if the product category successful complete
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        woo_product_categ = self.env['woo.product.categ.ept']
        product_category_obj = self.env['product.category']
        if category_id:
            ctg_list.append(category_id.id)
            self.create_categ_in_woo(category_id.parent_id, instance, woo_category_dict, ctg_list=ctg_list)
        else:
            for categ_id in list(OrderedDict.fromkeys(reversed(ctg_list))):
                if woo_category_dict.get((categ_id, instance)):
                    continue
                list_categ_id = product_category_obj.browse(categ_id)
                parent_category = list_categ_id.parent_id
                woo_product_parent_categ = parent_category and woo_product_categ.search(
                    [('name', '=', parent_category.name), ('woo_instance_id', '=', instance)],
                    limit=1) or False
                if woo_product_parent_categ:
                    woo_product_category = woo_product_categ.search([('name', '=', list_categ_id.name), (
                        'parent_id', '=', woo_product_parent_categ.id), ('woo_instance_id', '=',
                                                                         instance)], limit=1)
                    woo_category_dict.update({(categ_id, instance): woo_product_category.id})
                else:
                    woo_product_category = woo_product_categ.search(
                        [('name', '=', list_categ_id.name), ('woo_instance_id', '=', instance)],
                        limit=1)
                    woo_category_dict.update({(categ_id, instance): woo_product_category.id})
                if not woo_product_category:
                    if not parent_category:
                        parent_id = woo_product_categ.create(
                            {'name': list_categ_id.name, 'woo_instance_id': instance})
                        woo_category_dict.update({(categ_id, instance): parent_id.id})
                    else:
                        parent_id = woo_product_categ.search(
                            [('name', '=', parent_category.name),
                             ('woo_instance_id', '=', instance)], limit=1)
                        woo_cat_id = woo_product_categ.create(
                            {
                                'name': list_categ_id.name, 'woo_instance_id': instance,
                                'parent_id': parent_id.id
                            })
                        woo_category_dict.update({(categ_id, instance): woo_cat_id.id})
                elif not woo_product_category.parent_id and parent_category:
                    parent_id = woo_product_categ.search([('name', '=', parent_category.name), (
                        'parent_id', '=', woo_product_parent_categ.id),
                                                          ('woo_instance_id', '=', instance)])
                    if not parent_id:
                        woo_cat_id = woo_product_categ.create(
                            {'name': list_categ_id.name, 'woo_instance_id': instance})
                        woo_category_dict.update({(categ_id, instance): woo_cat_id.id})
                    if not parent_id.parent_id.id == woo_product_category.id and woo_product_categ.instance_id.id == \
                            instance:
                        woo_product_category.write({'parent_id': parent_id.id})
                        woo_category_dict.update({(categ_id, instance): parent_id.id})
        return woo_category_dict

    def update_category_info(self, categ_obj, instance_id):
        """
        This methos is used for create a new category in woo connector or update the existing category
        :param categ_obj: It contain the product category and its type is object
        :param instance_id: It contain the browsable object of the current instance
        :return: It will return browsable category object
        @author: Dipak Gogiya @Emipro Technologies Pvt. Ltd
        """
        woo_product_categ = self.env['woo.product.categ.ept']
        woo_categ_id = woo_product_categ.search([('name', '=', categ_obj.name), ('woo_instance_id', '=', instance_id)],
                                                limit=1)
        if woo_categ_id and woo_categ_id.name != categ_obj.name:
            woo_categ_id.write({'name': categ_obj.name})
        else:
            woo_categ_id = woo_product_categ.create(
                {'name': categ_obj.name, 'woo_instance_id': instance_id})
        return woo_categ_id
