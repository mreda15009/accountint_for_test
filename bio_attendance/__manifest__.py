{
    'name': "bio_attendance",
    'summary': """Biometric Attendance Download #######""",
    'description': """Biometric Attendance Download""",

    'author': 'ResalaSoft',
    'category': 'Resala/Human Resources',
    "license": "OPL-1",
    'website': 'http://www.resalasoft.com',

    'depends': ['base', 'hr', 'hr_attendance', 'hr_payroll_community'],

    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/security.xml',
        # Data
        'data/ir_cron.xml',
        # Biometric Views
        'views/biometric_record.xml',
        'views/biometric_log.xml',
        'views/biometric_machine.xml',
        'views/hr_payslip.xml',
        'views/menu.xml',
        # Inherited Views
        'views/hr_attendance.xml',
        'views/hr_employee.xml',
        # Wizard
        'wizard/configure_attendance.xml',
        'wizard/res_config_settings.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
}
