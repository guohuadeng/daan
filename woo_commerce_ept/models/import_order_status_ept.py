"""
For woo_commerce_ept module.
"""
from odoo import models, fields


class ImportOrderStatusEpt(models.Model):
    """
    Model for managing status of sale orders while importing from Woo commerce.
    @author: Maulik Barad on Date 02-Nov-2019.
    """
    _name = "import.order.status.ept"
    _description = "Woo Order Status"

    name = fields.Char()
    status = fields.Char()
