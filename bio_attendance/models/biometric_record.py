from odoo import api, fields, models, _


class BiometricRecord(models.Model):
    _name = 'biometric.record'
    _order = "name desc"

    name = fields.Datetime('Time')
    machine = fields.Many2one('biometric.machine', 'Machine Name')
    state = fields.Selection(
        [('success', 'Success'), ('failed', 'Failed')],
        default='success', tracking=True, string='Status', required=True, readonly=True, index=True, )
    note = fields.Char('Notes')
