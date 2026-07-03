from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAlertScenario(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"]._get("res.partner")
        cls.marker = "Business-Alerts-Test-Partner"
        cls.partner = cls.env["res.partner"].create({"name": cls.marker})

    def _make_alert(self, **overrides):
        vals = {
            "name": "Test alert",
            "model_id": self.partner_model.id,
            "alert_function": "count",
            "alert_type": "webhook",
            "webhook_url": "https://example.invalid/webhook",
            "records_domain": f"[('name', '=', '{self.marker}')]",
            "value": 1,
            "severity": "high",
        }
        vals.update(overrides)
        return self.env["alert.scenario"].create(vals)

    def test_count_alert_triggers_and_suspends(self):
        alert = self._make_alert()
        with patch("requests.post") as mock_post:
            alert.process_alerts()
        self.assertEqual(alert.state, "suspended")
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["AlertName"], "Test alert")
        self.assertEqual(payload["Severity"], "High")

    def test_count_alert_below_threshold_stays_enabled(self):
        alert = self._make_alert(value=999)
        with patch("requests.post") as mock_post:
            alert.process_alerts()
        self.assertEqual(alert.state, "enabled")
        mock_post.assert_not_called()

    def test_time_alert_triggers_on_old_record(self):
        # Backdate the record: create_date carries microseconds while
        # fields.Datetime.now() is second-truncated, so an age of ~0 can
        # evaluate negative and never trigger.
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = create_date - interval '2 hours'"
            " WHERE id = %s",
            [self.partner.id],
        )
        self.partner.invalidate_recordset(["create_date"])
        alert = self._make_alert(
            alert_function="time",
            time_frame=1,
            time_unit="hour",
            time_field_id=self.env["ir.model.fields"]._get(
                "res.partner", "create_date"
            ).id,
        )
        with patch("requests.post") as mock_post:
            alert.process_alerts()
        self.assertEqual(alert.state, "suspended")
        mock_post.assert_called_once()

    def test_webhook_without_url_does_not_crash(self):
        alert = self._make_alert(webhook_url=False)
        with patch("requests.post") as mock_post:
            alert.process_alerts()
        mock_post.assert_not_called()

    def test_cron_reset_suspended_alerts(self):
        alert = self._make_alert()
        alert.state = "suspended"
        self.env["alert.scenario"].cron_reset_suspended_alerts()
        self.assertEqual(alert.state, "enabled")
