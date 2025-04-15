from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    run_type = fields.Selection(related='company_id.run_type', readonly=False, )
    interval_number = fields.Integer(related='company_id.interval_number', readonly=False)
    interval_type = fields.Selection(related='company_id.interval_type', readonly=False)
    nextcall = fields.Datetime(related='company_id.nextcall', readonly=False)

    @api.onchange('run_type', 'interval_number', 'interval_type')
    def _onchange_get_attendance_from_bio_manual(self):
        cron = self.env.ref('bio_attendance.biometric_machine_download')

        if self.run_type == 'manual':
            cron.write({
                'active': False
            })
        else:
            cron.write({
                'active': True
            })

        cron.write({
            'interval_number': self.interval_number,
            'interval_type': self.interval_type,
            'nextcall': self.nextcall,
        })
