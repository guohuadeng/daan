"""
For woo_commerce_ept module.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import Warning

_logger = logging.getLogger("Woo")


class WooWebhookEpt(models.Model):
    """
    Model for storing webhooks created in woocommerce.
    @author: Maulik Barad on Date 30-Oct-2019.
    """
    _name = "woo.webhook.ept"
    _description = "Woo Webhook EPT"

    name = fields.Char(help="Name of Webhook created in woocommerce.", copy=False)
    woo_id = fields.Char(help="Id of webhook in woocommerce", copy=False, string="ID in Woo",
                         size=100)
    topic = fields.Selection([("order.created", "When Order is Created"),
                              ("order.updated", "When Order is Updated"),
                              ("order.deleted", "When Order is Deleted"),
                              ("product.created", "When Product is Created"),
                              ("product.updated", "When Product is Updated"),
                              ("product.deleted", "When Product is Deleted"),
                              ("product.restored", "When Product is Restored"),
                              ("customer.created", "When Customer is Created"),
                              ("customer.updated", "When Customer is Updated"),
                              ("customer.deleted", "When Customer is Deleted"),
                              ("coupon.created", "When Coupon is Created"),
                              ("coupon.updated", "When Coupon is Updated"),
                              ("coupon.deleted", "When Coupon is Deleted"),
                              ("coupon.restored", "When Coupon is Restored")],
                             string="Action",
                             help="Select action, when the webhook will be fired.")
    instance_id = fields.Many2one("woo.instance.ept", copy=False,
                                  help="Webhook created by this Woocommerce Instance.", ondelete="cascade")
    status = fields.Selection([("active", "Active"), ("paused", "Paused"), ("disabled", "Disabled")], copy=False, default="active",
                             help="Webhook statuses are :\nActive : delivers payload.\nPaused : delivery paused by admin.\nDisabled : delivery paused by failure.")
    delivery_url = fields.Char(help="URL where the webhook payload is delivered.")

    @api.model
    def create(self, vals):
        """
        Inherited for creating webhook in WooCommerce store for the same.
        @author: Maulik Barad on Date 20-Dec-2019.
        """
        available_webhook = self.search_read([("topic", "=", vals.get("topic")), ("instance_id", "=", vals.get("instance_id"))], ["id"])
        if available_webhook:
            raise Warning("Webhook already exists for selected action. You can't create webhook with same action.\nAction must be unique for the Instance.")
        res = super(WooWebhookEpt, self).create(vals)
        res.get_webhook()
        return res

    def unlink(self):
        """
        Inherited method for deleting the webhooks from WooCommerce Store.
        @author: Maulik Barad on Date 20-Dec-2019.
        """
        webhook_ids = self.mapped("woo_id")
        if webhook_ids:
            wcapi = self.instance_id.woo_connect()
            data = {"delete":webhook_ids}

            response = wcapi.post("webhooks/batch", data)
            if response.status_code not in [200, 201]:
                raise Warning("Something went wrong while deleting the webhook.\n" + str(response.status_code) + "\n" + response.reason)

        _logger.info("Webhook deleted successfully.")
        return super(WooWebhookEpt, self).unlink()

    def toggle_status(self, status=False):
        """
        Toggles the webhook status between Active and Paused in woocommerce.
        @author: Maulik Barad on Date 01-Nov-2019.
        """
        wcapi = self.instance_id.woo_connect()
        for hook in self:
            status = status if status else "paused" if hook.status == "active" else "active"
            response = wcapi.put("webhooks/" + str(hook.woo_id), {"status": status})
            if response.status_code in [200, 201]:
                hook.status = status
            else:
                raise Warning("Something went wrong while changing status of the webhook.\n" + str(response.status_code) + "\n" + response.reason)
        _logger.info("Webhook status changed.")
        return True

    def get_delivery_url(self):
        """
        Gives delivery URL for the webhook as per the topic.
        @author: Maulik Barad on Date 20-Dec-2019.
        """
        topic = self.topic
        if topic == "order.created":
            delivery_url = self.get_base_url() + "/create_order_webhook_odoo"
        elif topic == "order.updated":
            delivery_url = self.get_base_url() + "/update_order_webhook_odoo"
        elif topic == "order.deleted":
            delivery_url = self.get_base_url() + "/delete_order_webhook_odoo"
        elif topic == "product.created":
            delivery_url = self.get_base_url() + "/create_product_webhook_odoo"
        elif topic == "product.updated":
            delivery_url = self.get_base_url() + "/update_product_webhook_odoo"
        elif topic == "product.deleted":
            delivery_url = self.get_base_url() + "/delete_product_webhook_odoo"
        elif topic == "product.restored":
            delivery_url = self.get_base_url() + "/restore_product_webhook_odoo"
        elif topic == "customer.created":
            delivery_url = self.get_base_url() + "/create_customer_webhook_odoo"
        elif topic == "customer.updated":
            delivery_url = self.get_base_url() + "/update_customer_webhook_odoo"
        elif topic == "customer.deleted":
            delivery_url = self.get_base_url() + "/delete_customer_webhook_odoo"
        elif topic == "coupon.created":
            delivery_url = self.get_base_url() + "/create_coupon_webhook_odoo"
        elif topic == "coupon.updated":
            delivery_url = self.get_base_url() + "/update_coupon_webhook_odoo"
        elif topic == "coupon.deleted":
            delivery_url = self.get_base_url() + "/delete_coupon_webhook_odoo"
        elif topic == "coupon.restored":
            delivery_url = self.get_base_url() + "/restore_coupon_webhook_odoo"
        return delivery_url

    def get_webhook(self):
        """
        Creates webhook in WooCommerce Store for webhook in Odoo if no webhook is
        there, otherwise updates status of the webhook, if it exists in WooCommerce store.
        @author: Maulik Barad on Date 20-Dec-2019.
        """
        topic = self.topic
        instance = self.instance_id
        wcapi = instance.woo_connect()
        delivery_url = self.get_delivery_url()

        webhook_data = {
            "name":self.name,
            "topic":topic,
            "status":"active",
            "delivery_url":delivery_url
            }
        if self.woo_id:
            # Checks for available webhook. Updates status if available otherwise deletes the webhook in Odoo.
            response = wcapi.get("webhooks/" + str(self.woo_id))
            if response.status_code == 200:
                self.status = response.json().get("status")
            else:
                self.woo_id = 0
                self.sudo().unlink()
            return True

        response = wcapi.post("webhooks", webhook_data)
        if response.status_code in [200, 201]:
            new_webhook = response.json()
            self.write({"woo_id":new_webhook.get("id"), "status":new_webhook.get("status"), "delivery_url":delivery_url})
            _logger.info("Webhook created successfully.")
            return True
        raise Warning("Something went wrong while creating the webhook.\n" + str(response.status_code) + "\n" + response.reason)
