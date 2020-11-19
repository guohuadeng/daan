# -*- encoding: utf-8 -*-
import json
import ast
import logging
from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class ServerActions(models.Model):

    _inherit = 'ir.actions.server'

    # ----------------------------------------------------------
    # Functions
    # ----------------------------------------------------------

    @api.model
    def _get_eval_context(self, action=None):
        eval_context = super(
            ServerActions, self)._get_eval_context(action=action)
        eval_context.update({
            'mb': {
                'json': json,
                'ast': ast
            }
        })
        return eval_context
