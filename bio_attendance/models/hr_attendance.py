from datetime import datetime

from odoo import models, fields, api, _
from odoo.tools import format_datetime
from odoo.exceptions import ValidationError

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    user = fields.Char(string="User No", related="employee_id.att_user_id")
    state = fields.Selection(
        selection=[('fixin', 'Fix In'), ('fixout', 'Fix Out'), ('right', 'Right')],
        default='right',
        help='The user did not register an input '
             'or an output in the correct order, '
             'then the system proposed one or more regiters to fix the problem '
             'but you must review the created register due '
             'because of hour could be not correct')

    @api.model
    def _cron_send_notification(self):
        atts = self.search([('state', '!=', 'right')])
        atts.send_notification()

    def send_notification(self):
        for att in self:
            att_date = datetime.strftime(datetime.strptime(str(att.check_in), DATETIME_FORMAT), DATE_FORMAT)
            if att.state == 'right':
                continue
            employee = att.employee_id
            partners = self.env['res.partner']

            mail_content = "  Hello  " + employee.name + ",<br>Your Attendance in " + att_date + "  Need To Be Fixed " + ". Please Check  it <br> Regards"
            main_content = {
                'subject': _('Wrong Attendance Notification'),
                'author_id': self.env.user.partner_id.id,
                'body_html': mail_content,
                'email_to': self.env.user.partner_id.email,
                # 'recipient_ids': [(4, employee.address_home_id.id)],

            }
            self.env['mail.mail'].sudo().create(main_content).send()

            for user in self.env['res.users'].search([]):
                if user.has_group('bio_attendance.group_wrong_attendance_notify'):
                    partners += user.partner_id
            mail_content = _('Dear Sir,'
                             '<br> Attendance of Employee:%s  In  date :%s Need to be fixed Please Check.<br> '
                             'Regards<br>'
                             ) % (employee.name, att_date)
            main_content = {
                'subject': _('Wrong Attendance Of :%s  at %s') % (employee.name, att_date),
                'author_id': self.env.user.partner_id.id,
                'body_html': mail_content,
                'recipient_ids': [(4, pid) for pid in partners.ids],
            }
            self.env['mail.mail'].sudo().create(main_content).send()

    def fix_register(self):
        self.write({'state': 'right'})

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """ Verifies the validity of the attendance record compared to the others from the same employee.
            For the same employee we must have :
                * maximum 1 "open" attendance record (without check_out)
                * no overlapping time slices with previous employee records
        """
        for attendance in self:
            # we take the latest attendance before our check_in time and check it doesn't overlap with ours
            last_attendance_before_check_in = self.env['hr.attendance'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('check_in', '<=', attendance.check_in),
                ('id', '!=', attendance.id),
            ], order='check_in desc', limit=1)
            if last_attendance_before_check_in and last_attendance_before_check_in.check_out and last_attendance_before_check_in.check_out > attendance.check_in:
                raise ValidationError(
                    _("Cannot create new attendance record for %(empl_name)s,"
                      " the employee was already checked in on %(datetime)s") % {
                        'empl_name': attendance.employee_id.name,
                        'datetime': format_datetime(self.env, attendance.check_in, dt_format=False),
                    })
            if not attendance.check_out:
                # if our attendance is "open" (no check_out), we verify there is no other "open" attendance
                no_check_out_attendances = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_out', '=', False),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if no_check_out_attendances:
                    no_check_out_attendances.write({
                        'check_out': no_check_out_attendances.check_in,
                        'state': 'fixout'
                    })
            else:
                # we verify that the latest attendance with check_in time before our check_out time
                # is the same as the one before our check_in time computed before, otherwise it overlaps
                last_attendance_before_check_out = self.env['hr.attendance'].search([
                    ('employee_id', '=', attendance.employee_id.id),
                    ('check_in', '<', attendance.check_out),
                    ('id', '!=', attendance.id),
                ], order='check_in desc', limit=1)
                if last_attendance_before_check_out and last_attendance_before_check_in != last_attendance_before_check_out:
                    raise ValidationError(
                        _("Cannot create new attendance record for %(empl_name)s,"
                          " the employee was already checked in on %(datetime)s") % {
                            'empl_name': attendance.employee_id.name,
                            'datetime': format_datetime(self.env, last_attendance_before_check_out.check_in,
                                                        dt_format=False),
                        })
