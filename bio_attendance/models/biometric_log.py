from odoo import api, fields, models, _


class BiometricLog(models.Model):
    _name = 'biometric.log'
    _order = "name desc"

    name = fields.Datetime('Time')
    user = fields.Char('User No')
    employee_id = fields.Many2one('hr.employee', 'Employee')
    machine = fields.Many2one('biometric.machine', 'Machine Name')
    type = fields.Selection([('in', 'In'), ('out', 'Out')], default='in')
