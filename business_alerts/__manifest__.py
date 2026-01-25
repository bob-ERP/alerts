{
    "name": "Business Alerts",
    "summary": "Send alerts to n8n",
    "version": "18.0.1.0.2",
    "category": "Technical",
    "author": "bobco GmbH",
    "maintainers": [
        "ilyas",
        "Philip B.",
        "achulii",
    ],
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/alert_scenario_views.xml",
        "views/res_config_settings_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": True,
}
