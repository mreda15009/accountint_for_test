from odoo import api, fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    att_user_id = fields.Char("Attendance User ID")

