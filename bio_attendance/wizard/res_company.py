from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"

    def default_nextcall(self):
        return (fields.Datetime.now()).replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')

    run_type = fields.Selection(
        string="Get Biometric Logs", selection=[('manual', 'Manual'), ('auto', 'Automatic')], default='manual')
    interval_number = fields.Integer(string="Interval Number", default=1, )
    interval_type = fields.Selection(string="Interval Type",
                                     selection=[('minutes', 'Minutes'),
                                                ('hours', 'Hours'),
                                                ('days', 'Days'),
                                                ('weeks', 'Weeks'),
                                                ('months', 'Months')],
                                     default='days')
    nextcall = fields.Datetime(string="Call Time", default=lambda self: self.default_nextcall())
