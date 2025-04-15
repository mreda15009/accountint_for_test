import pytz
import logging
from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.addons.bio_attendance.zk import ZK, const

_logger = logging.getLogger(__name__)
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


def convert_date_to_utc(date, tz):
    try:
        local = pytz.timezone(tz)
        date = local.localize(date, is_dst=None)
        date = date.astimezone(pytz.utc)
        date.strftime('%Y-%m-%d: %H:%M:%S')
        return date.replace(tzinfo=None)
    except Exception:
        return date


def convert_date_to_local(date, tz):
    local = pytz.timezone(tz)
    date = date.replace(tzinfo=pytz.utc)
    date = date.astimezone(local)
    date.strftime('%Y-%m-%d: %H:%M:%S')
    return date.replace(tzinfo=None)


class BiometricMachine(models.Model):
    _name = 'biometric.machine'

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]

    name = fields.Char('Name')
    ip_address = fields.Char('Ip address')
    type = fields.Selection(
        string="Machine Type",
        selection=[('in', 'In Only'), ('out', 'Out Only'), ('inout', 'In/Out')], required=True,
        default='inout')
    port = fields.Integer('Port', default=4370)
    sequence = fields.Integer('Sequence')
    timezone = fields.Selection(
        _tz_get, 'Timezone', size=64, help='Device timezone', default=lambda self: self.env.user.tz
    )
    log_ids = fields.One2many(comodel_name="biometric.record", inverse_name="machine", string="Log", required=False, )
    time_interval_min = fields.Integer(
        'Min time', help='Min allowed time  between two registers', default=1)
    interval_min = fields.Selection(
        [('sec', 'Sec(s)'), ('min', 'Min(s)'), ('hour', 'Hour(s)'), ('days', 'Day(s)'), ],
        'Min allowed time', help='Min allowed time between two registers', default='sec')
    time_interval_max = fields.Integer(
        'Max time', help='Max allowed time  between two registers', default=1)
    interval_max = fields.Selection(
        [('sec', 'Sec(s)'), ('min', 'Min(s)'), ('hour', 'Hour(s)'), ('days', 'Day(s)'), ],
        'Max allowed time', help='Max allowed time between two registers', default='days')
    state = fields.Selection(
        [('active', 'Active'), ('inactive', 'InActive')], default='inactive',
        tracking=True, string='Status', required=False, index=True, )

    attendance_log_ids = fields.One2many('biometric.log', 'machine', 'Logs')

    att_log_cnt = fields.Integer(compute='_compute_attendance_log_cnt')

    def action_activate_machine(self):
        for mc in self:
            mc.state = 'active'

    @property
    def min_time(self):
        # Get min time
        if self.interval_min == 'sec':
            min_time = timedelta(seconds=self.time_interval_min)
        elif self.interval_min == 'min':
            min_time = timedelta(minutes=self.time_interval_min)
        elif self.interval_min == 'hour':
            min_time = timedelta(hours=self.time_interval_min)
        else:
            min_time = timedelta(days=self.time_interval_min)
        return min_time

    @property
    def max_time(self):
        # Get min time
        if self.interval_max == 'sec':
            max_time = timedelta(seconds=self.time_interval_max)
        elif self.interval_max == 'min':
            max_time = timedelta(minutes=self.time_interval_max)
        elif self.interval_max == 'hour':
            max_time = timedelta(hours=self.time_interval_max)
        else:
            max_time = timedelta(days=self.time_interval_max)
        return max_time

    @api.model
    def _cron_att_download(self):
        for mc in self.search([('state', '=', 'active')]):
            mc.download_log()
        self.download_from_log()

    @api.model
    def _cron_check_connection(self):
        for mc in self.search([('state', '=', 'active')]):
            mc.check_notification()

    def check_notification(self):
        for mc in self:
            now = datetime.strftime(datetime.now(), DATETIME_FORMAT)
            yesterday = datetime.strftime(datetime.now() + timedelta(days=-1), DATETIME_FORMAT)
            records = self.env['biometric.record'].search(
                [('machine', '=', mc.id), ('name', '>=', yesterday), ('name', '<=', now)])

            if any([r.state != 'failed' for r in records]):
                continue

            if mc.state != 'active':
                continue

            partners = self.env['res.partner']

            for user in self.env['res.users'].search([]):
                if user.has_group('bio_attendance.group_check_bio_attendance'):
                    partners += user.partner_id
            if partners:
                mail_content = _(
                    'Dear Sir,'
                    '<br>'
                    'Attendance Biometric Machine:%s Has connection Error Please Check.<br> '
                    'Regards'
                    '<br>'
                ) % mc.name
                main_content = {
                    'subject': _('Connection Error For Biometric Machine Of :%s ') % mc.name,
                    'author_id': self.env.user.partner_id.id,
                    'body_html': mail_content,
                    'recipient_ids': [(4, pid) for pid in partners.ids],
                }
                self.env['mail.mail'].sudo().create(main_content).send()

    def _compute_attendance_log_cnt(self):
        for machine in self:
            machine.att_log_cnt = len(machine.attendance_log_ids)

    def action_view_attendance_log(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('bio_attendance.action_biometric_log_view')
        action['domain'] = [('machine', '=', self.id)]
        return action

    def download_log(self):
        for machine in self:
            machine_ip = machine.ip_address
            port = machine.port
            zk = ZK(machine_ip, int(port), timeout=90, ommit_ping=True)
            record_vals = {'name': datetime.now(), 'machine': machine.id}
            try:
                res = zk.connect()
                if res:
                    attendance = res.get_attendance()
                    if attendance:
                        try:
                            self.action_create_log(attendance, machine.id)
                            record_vals['state'] = 'success'
                            record_vals['note'] = 'successful connection and attendance logs have been updated'
                            self.env['biometric.record'].sudo().create(record_vals)
                        except Exception as e:
                            zk.enableDevice()
                            try:
                                zk.disconnect()
                            except BaseException as exp:
                                _logger.info("++++++++++++Exception++++++++++++++++++++++", exp)

                            record_vals['state'] = 'failed'
                            record_vals[
                                'note'] = 'Successful Connection But there is error while writing attendance logs as the error is **%s**' % e
                            self.env['biometric.record'].sudo().create(record_vals)
                    else:
                        record_vals['state'] = 'success'
                        record_vals['note'] = 'successful connection but there is no attendance logs'
                        self.env['biometric.record'].sudo().create(record_vals)
            except Exception as exps:
                _logger.info("++++++++++++Exception++++++++++++++++++++++", exps)
                record_vals['state'] = 'failed'
                record_vals[
                    'note'] = 'Failed ,please check the parameters and network connections. (Machine Not Connected)'
                self.env['biometric.record'].sudo().create(record_vals)

    def download_from_log(self):
        logs = self.env['biometric.log'].search([])
        for log in logs.sorted(key=lambda l: l.name):
            type = 0
            if log.type == 'in':
                type = 0
            if log.type == 'out':
                type = 1
            if log.machine:
                tz_info = log.machine.timezone
                local_atttime = convert_date_to_local(log.name, tz_info)
                record_vals = {'name': datetime.now()}
                att = [log.employee_id.att_user_id, False, local_atttime, type]
                try:
                    log.machine.prepare_vals_to_create_attendance([att])
                except Exception as e:
                    _logger.info("++++++++++++Exception++++++++++++++++++++++", e)
                    record_vals['state'] = 'failed'
                    record_vals[
                        'note'] = 'Successful Connection But there is error while writing attendances from logs as -->log time:%s  log employee:%s the error is **%s**' % (
                        e, log.name, log.employee_id.name)
                    self.env['biometric.record'].sudo().create(record_vals)
                    break

    def action_download_from_log(self):
        self.download_from_log()
        employee_ids = self.env['hr.employee'].search([('att_user_id', '!=', False), ('att_user_id', '>', 0)])
        for employee in employee_ids:
            employee.convert_log_to_attendance()

    def prepare_vals_to_create_attendance(self, bio_attendances):
        employee_obj = self.env['hr.employee']
        for res in self:
            tz_info = res.timezone
            att_users = []
            users_atts = {}
            if not bio_attendances:
                continue
            bio_attendances.sort(key=lambda b: b[2])

            for att in bio_attendances:
                user_no = att[0]
                employee = employee_obj.search([('att_user_id', '=', user_no)], limit=1)
                att_time = att[2]
                time_utc = convert_date_to_utc(att_time, tz_info)
                att_type = att[3]

                if not employee:
                    continue
                    employee = employee_obj.create({
                        'name': 'Undefined user ID ' + str(user_no),
                        'att_user_id': user_no
                    })
                min_time = res.min_time
                str_att_time_utc = datetime.strftime(convert_date_to_utc(att_time, tz_info), DATETIME_FORMAT)
                emp_prev_atts = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', employee.id), ('check_in', '>=', str_att_time_utc)], order='check_in DESC')
                if emp_prev_atts:
                    continue
                prev_att = self.env['hr.attendance'].search([
                    ('employee_id.id', '=', employee.id),
                    ('check_in', '<', str_att_time_utc)
                ], limit=1, order='check_in DESC', )
                if prev_att and prev_att.check_out:
                    checkout_time = prev_att.check_out
                    if checkout_time >= time_utc:
                        continue
                elif prev_att and not prev_att.check_out:
                    checkin_time = prev_att.check_in
                    if att_type == 0:
                        if min_time >= (time_utc - checkin_time):
                            continue
                if user_no not in att_users:
                    users_atts[user_no] = []
                    att_users.append(user_no)
                users_atts[user_no].append((att_time, att_type))
            for user, atts in users_atts.items():
                employee = employee_obj.search([('att_user_id', '=', user)], limit=1)
                attendances = sorted(atts, key=lambda t: t[0])
                if attendances:
                    for user_att in attendances:
                        res.create_attendance(employee.id, user_att[0], user_att[1])

    def create_attendance(self, emp_id, time, type):
        att_obj = self.env['hr.attendance']
        for res in self:
            tz_info = res.timezone
            if emp_id and time and type in (0, 1):
                time_utc = convert_date_to_utc(time, tz_info)
                str_att_time_utc = datetime.strftime(convert_date_to_utc(time, tz_info), DATETIME_FORMAT)
                max_time = res.max_time
                min_time = res.min_time
                prev_att = self.env['hr.attendance'].search([
                    ('employee_id.id', '=', emp_id),
                    ('check_in', '<=', str_att_time_utc)],
                    limit=1,
                    order='check_in DESC', )
                if not prev_att:
                    if type == 0:
                        att_obj.create({
                            'employee_id': emp_id,
                            'check_in': str_att_time_utc,
                            'state': 'right'
                        })
                    elif type == 1:
                        new_time = time_utc - timedelta(milliseconds=1)
                        str_new_time_utc = datetime.strftime(new_time, DATETIME_FORMAT)
                        att_obj.create({
                            'employee_id': emp_id,
                            'check_in': str_new_time_utc,
                            'check_out': str_att_time_utc,
                            'state': 'fixin'
                        })
                else:
                    if prev_att.check_out:
                        checkout_time = prev_att.check_out
                        if checkout_time >= time_utc:
                            continue
                        if type == 0:
                            att_obj.create({
                                'employee_id': emp_id,
                                'check_in': str_att_time_utc,
                                'state': 'right'
                            })
                        elif type == 1:
                            if checkout_time >= (time_utc - min_time):
                                prev_att.write({
                                    'check_out': str_att_time_utc,
                                })
                            else:

                                new_checkin_time = time_utc - timedelta(milliseconds=1)
                                att_obj.create({
                                    'employee_id': emp_id,
                                    'check_in': datetime.strftime(new_checkin_time, DATETIME_FORMAT),
                                    'check_out': str_att_time_utc,
                                    'state': 'fixin'
                                })
                    else:
                        checkin_time = prev_att.check_in
                        if checkin_time >= time_utc:
                            continue
                        if type == 0:
                            if min_time >= (time_utc - checkin_time):
                                continue
                            str_new_checkout_time = datetime.strftime(
                                checkin_time + timedelta(milliseconds=1), DATETIME_FORMAT)

                            prev_att.write({
                                'check_out': str_new_checkout_time,
                                'state': 'fixout'
                            })
                            att_obj.create({
                                'employee_id': emp_id,
                                'check_in': str_att_time_utc,
                            })
                        elif type == 1:
                            if max_time >= (time_utc - checkin_time):
                                prev_att.write({
                                    'check_out': str_att_time_utc,
                                })
                            else:
                                new_time = time_utc - timedelta(milliseconds=1)
                                str_new_time_utc = datetime.strftime(new_time, DATETIME_FORMAT)

                                str_new_checkout_time = datetime.strftime(
                                    checkin_time + timedelta(milliseconds=1), DATETIME_FORMAT)
                                prev_att.write({
                                    'check_out': str_new_checkout_time,
                                    'state': 'fixout'
                                })

                                att_obj.create({
                                    'employee_id': emp_id,
                                    'check_in': str_new_time_utc,
                                    'check_out': str_att_time_utc,
                                    'state': 'fixin'
                                })

    def action_create_log(self, atts, machine_id):
        if not atts:
            return
        for res in self:
            employee_obj = self.env['hr.employee']
            log_obj = self.env['biometric.log']
            machine = self.env['biometric.machine'].browse(machine_id)
            if not machine:
                continue

            for i, att in enumerate(atts):
                employee = employee_obj.search([('att_user_id', '=', att.user_id)], limit=1)
                str_att_time_utc = datetime.strftime(convert_date_to_utc(att.timestamp, res.timezone), DATETIME_FORMAT)
                if not employee:
                    continue
                prev_log = self.env['biometric.log'].search([
                    ('employee_id', '=', employee.id),
                    ('name', '>=', str_att_time_utc),
                    ('machine', '=', machine_id)],
                    limit=1
                )
                if prev_log:
                    continue
                att_type = att.punch
                type_att = 'in'
                if att_type == 1:
                    type_att = 'out'

                log_obj.sudo().create({
                    'user': att.user_id,
                    'employee_id': employee.id,
                    'name': str_att_time_utc,
                    'machine': machine_id,
                    'type': type_att if machine.type == 'inout' else machine.type
                })
