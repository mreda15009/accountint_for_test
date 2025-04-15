from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    branch_info = fields.Text(string="Branch Info", compute='_compute_branch_info')

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_branch_info(self):
        for rec in self:
            data = {}
            logs = self.env['biometric.log'].search(
                [
                    ('employee_id', '=', rec.employee_id.id),
                    ('name', '>=', rec.date_from),
                    ('name', '<=', rec.date_to),
                    ('type', '=', 'in')
                ])
            for log in logs:
                data.setdefault(log.machine.name, 0)
                if log.machine.name in data:
                    data[log.machine.name] += 1
                else:
                    data[log.machine.name] = 1

            branch_info = ""
            for branch, num_of_days in data.items():
                branch_info += f"Attend in ( {branch} ) branch {num_of_days} days \n"

            rec.branch_info = branch_info
