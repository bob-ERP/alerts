from odoo import fields, models


class ResConfigSettigs(models.TransientModel):
    _inherit = "res.config.settings"

    alerts_evaluation = fields.Boolean(
        string="Alerts Evaluation",
        config_parameter="business_alerts.alerts_evaluation",
    )
    reset_suspended_alerts = fields.Boolean(
        string="Reset Suspended Alerts",
        config_parameter="business_alerts.reset_suspended_alerts",
    )
    evaluation_time_frame = fields.Integer(
        string="Run Every",
        config_parameter="business_alerts.time_frame",
    )
    evaluation_time_unit = fields.Selection(
        string="Interval Unit",
        selection=[
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
        ],
        config_parameter="business_alerts.time_unit",
    )

    reset_suspended_alerts_time_frame = fields.Integer(
        string="Run Every",
        config_parameter="business_alerts.reset_suspended_alerts_time_frame",
    )
    reset_suspended_alerts_time_unit = fields.Selection(
        string="Interval Unit",
        selection=[
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
            ("weeks", "Weeks"),
            ("months", "Months"),
        ],
        config_parameter="business_alerts.reset_suspended_alerts_time_unit",
    )

    def set_values(self):
        super().set_values()
        alerts_evaluation_cron_id = self.env.ref("business_alerts.alerts_cron")
        reset_suspended_alerts_cron_id = self.env.ref(
            "business_alerts.cron_reset_suspended_alerts"
        )
        alerts_evaluation_cron_id.write(
            {
                "active": self.alerts_evaluation,
                "interval_number": self.evaluation_time_frame,
                "interval_type": self.evaluation_time_unit,
            }
        )
        reset_suspended_alerts_cron_id.write(
            {
                "active": self.reset_suspended_alerts,
                "interval_number": self.reset_suspended_alerts_time_frame,
                "interval_type": self.reset_suspended_alerts_time_unit,
            }
        )
