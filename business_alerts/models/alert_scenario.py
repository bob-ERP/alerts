import logging

import requests
from odoo import _, fields, models
from odoo.tools.safe_eval import safe_eval, wrap_module
from werkzeug.urls import url_join

_log = logging.getLogger(__name__)


class AlertScenario(models.Model):
    _name = "alert.scenario"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Alert Scenarios"

    name = fields.Char(
        required=True,
        tracking=True,
        help="Short, human-readable title for this alert; used in lists and chatter logs.",
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help="When off, the scenario is archived and skipped by scheduled jobs.",
    )
    state = fields.Selection(
        [("enabled", "Enabled"), ("suspended", "Suspended")],
        required=True,
        default="enabled",
        tracking=True,
        help="Lifecycle of the alert (Enabled or Suspended). Alerts set themselves to Suspended after firing; reset manually or via the “Reset Suspended Alerts” scheduled job.",
    )
    alert_function = fields.Selection(
        [
            ("count", "Count (number of matching records)"),
            (
                "time",
                "Time (age since the last matching record by a date/datetime field)",
            ),
        ],
        tracking=True,
        help="How the alert is evaluated: Count (number of matching records) or Time (age since the last matching record by a date/datetime field).",
    )

    time_frame = fields.Integer(
        tracking=True,
        help="Threshold value for Time alerts; triggers when the time since the last matching record is greater than or equal to this value.",
    )
    time_unit = fields.Selection(
        [
            ("second", "Seconds"),
            ("minute", "Minutes"),
            ("hour", "Hours"),
            ("day", "Days"),
            ("year", "Years"),
        ],
        tracking=True,
        help="Unit for the Time Frame (seconds, minutes, hours, days, years).",
    )
    time_field_id = fields.Many2one(
        "ir.model.fields",
        tracking=True,
        help="Date/Datetime field on the selected Model used to measure elapsed time for Time alerts.",
    )
    value = fields.Integer(
        "Trigger Value",
        tracking=True,
        help="For Count alerts, the minimum number of records that must match the domain to trigger (≥ this number).",
    )
    records_domain = fields.Text(
        tracking=True,
        help="Rule that selects the records to evaluate on the chosen Model."
        "Advanced: supports datetime in expressions (e.g., ['&', ('state','=','error'), ('create_date','<', datetime.datetime.now()-datetime.timedelta(hours=1))]).",
    )
    notification = fields.Text(
        tracking=True,
        help="Message text sent to the webhook when the alert triggers",
    )
    severity = fields.Selection(
        [("high", "High"), ("medium", "Medium"), ("low", "Low")],
        required=True,
        default="medium",
        tracking=True,
        help="Importance label included in the alert payload (High/Medium/Low).",
    )
    webhook_url = fields.Char(
        "Webhook URL",
        tracking=True,
        help="Destination endpoint (e.g., n8n webhook) that receives a JSON POST with alert details.",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        tracking=True,
        help="The Odoo model to monitor; determines the records and fields available for this alert.",
    )
    model = fields.Char(
        string="Related Document Model",
        related="model_id.model",
        tracking=True,
    )
    action_id = fields.Many2one(
        "ir.actions.act_window",
        string="Action",
        tracking=True,
        help="Odoo window action used to build the URL included in the alert; clicking the link opens this view.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible User",
        tracking=True,
        help="User responsible for this alert; their name, email, and phone are sent with the alert payload.",
    )
    alert_type = fields.Selection(
        [("webhook", "Webhook"), ("email", "Email")],
        required=True,
        default="webhook",
        tracking=True,
        help="Method used to send the alert: Webhook or Email (using an email template).",
    )
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        tracking=True,
    )

    def cron_trigger_alert_jobs(self):
        alerts = self.env["alert.scenario"].search([("state", "=", "enabled")])
        if alerts:
            alerts.process_alerts()
            _log.info("Alert scenarios processed: %s", "\n".join(alerts.mapped("name")))

    def cron_reset_suspended_alerts(self):
        alerts = self.env["alert.scenario"].search([("state", "=", "suspended")])
        alerts.write({"state": "enabled"})

    def send_alert(self, record=None, msg=None, url=None):
        if self.alert_type == "webhook":
            if not self.webhook_url:
                _log.warning("Alert URL is not set. %s", self.name)
                return
            web_base_url = (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            record_odoo_url = ""
            if not msg:
                msg = self.notification
            if record:
                record_odoo_url = url_join(
                    web_base_url,
                    f"/web#id={record.id}&model={record._name}&view_type=form",
                )
            try:
                post_res = requests.post(
                    self.webhook_url,
                    json={
                        "AlertName": self.name,
                        "Message": msg,
                        "Client": self.env.company.display_name,
                        "AlertType": "Warning",
                        "Severity": self.severity.capitalize(),
                        "URL": record_odoo_url or url,
                        "AlertAge": "",
                        "Name": self.user_id.partner_id.name if self.user_id else "",
                        "Email": self.user_id.partner_id.email if self.user_id else "",
                        "Phone": self.user_id.partner_id.phone if self.user_id else "",
                    },
                    timeout=30,
                )
                return post_res
            except Exception as e:
                _log.error("Cant send error alert. Please check Alert URL. %s", e)
        else:
            if not self.mail_template_id:
                _log.warning("Email template is not set. %s", self.name)
                return
            self.mail_template_id.send_mail(
                self.id,
                force_send=True,
            )

    def _get_url_by_action(self, view_type="list"):
        web_base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        try:
            action = self.action_id
            url = url_join(
                web_base_url,
                f"/web#action={action.id}&model={action.res_model}&view_type={view_type}",
            )
            return url
        except:
            return web_base_url

    def process_alerts(self):
        datetime = wrap_module(
            __import__("datetime"),
            [
                "date",
                "datetime",
                "time",
                "timedelta",
                "timezone",
                "tzinfo",
                "MAXYEAR",
                "MINYEAR",
            ],
        )
        time_unit_map = {
            "second": lambda td: td.total_seconds(),
            "minute": lambda td: td.total_seconds() / 60,
            "hour": lambda td: td.total_seconds() / 3600,
            "day": lambda td: td.days,
            "year": lambda td: td.days / 365.25,
        }
        for record in self:
            domain = safe_eval(record.records_domain, {"datetime": datetime})
            url = record._get_url_by_action()

            # Count Alert
            if record.alert_function == "count":
                if len(self.env[record.model].search(domain)) >= record.value:
                    send_alert_res = record.send_alert(url=url)
                    record.state = "suspended"
                    record.message_post(body=f"Alert has been sent: {send_alert_res}")
                    _log.info("Count alert triggered: %s", record.name)
                continue

            # Time Alert
            elif record.alert_function == "time":
                if not record.time_field_id:
                    _log.warning("Time field is not set. %s", record.name)
                    return
                if not record.time_unit:
                    _log.warning("Time unit is not set. %s", record.name)
                    return

                last_record = self.env[record.model].search(
                    domain, order="id desc", limit=1
                )
                if not last_record:
                    _log.warning("There is no records. %s", record.name)
                    return

                time_val = getattr(last_record, record.time_field_id.name, None)
                if not time_val:
                    _log.warning("Time field value missing. %s", record.name)
                    continue
                converter = time_unit_map.get(record.time_unit)
                if not converter:
                    _log.warning(
                        "Unsupported time unit '%s'. %s", record.time_unit, record.name
                    )
                    continue
                diff = converter(fields.Datetime.now() - time_val)
                if diff >= record.time_frame:
                    send_alert_res = record.send_alert(url=url)
                    record.state = "suspended"
                    record.message_post(body=f"Alert has been sent: {send_alert_res}")
                    _log.info("Time alert triggered: %s", record.name)
