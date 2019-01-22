from mock import patch

from cabot.cabotapp.tests.tests_basic import LocalTestCase
from cabot.cabotapp.models import Service
from cabot_alert_mattermost import models
from cabot.cabotapp.alert import update_alert_plugins

class TestMattermostAlerts(LocalTestCase):
    def setUp(self):
        super(TestMattermostAlerts, self).setUp()

        self.mattermost_user_data = models.MattermostAlertUserData.objects.create(
            mattermost_alias ="test_user_mattermost_alias",
            user = self.user.profile,
            title=models.MattermostAlertUserData.name,
            )
        self.mattermost_user_data.save()

        self.service.users_to_notify.add(self.user)

        update_alert_plugins()
        self.mattermost_plugin = models.MattermostAlert.objects.get(title=models.MattermostAlert.name)
        self.service.alerts.add(self.mattermost_plugin)
        self.service.save()
        self.service.update_status()

    def test_users_to_notify(self):
        self.assertEqual(self.service.users_to_notify.all().count(), 1)
        self.assertEqual(self.service.users_to_notify.get(pk=1).username, self.user.username)

    @patch('cabot_alert_mattermost.models.MattermostAlert._send_mattermost_alert')
    def test_normal_alert(self, fake_mattermost_alert):
        self.service.overall_status = Service.PASSING_STATUS
        self.service.old_overall_status = Service.ERROR_STATUS
        self.service.save()
        self.service.alert()
        fake_mattermost_alert.assert_called_with(u"""\
[Service Service](http://localhost/service/1/) is back to normal :ok_hand:

 @test_user_mattermost_alias\
""", sender='Cabot/Service')

    @patch('cabot_alert_mattermost.models.MattermostAlert._send_mattermost_alert')
    def test_failure_alert(self, fake_mattermost_alert):
        # Most recent failed
        self.service.overall_status = Service.CRITICAL_STATUS
        self.service.old_overall_status = Service.PASSING_STATUS
        self.service.save()
        self.service.alert()
        fake_mattermost_alert.assert_called_with(u"""\
**[Service Service](http://localhost/service/1/) is reporting CRITICAL status** :fire:

 @test_user_mattermost_alias

| Check | Error |
|:------|:------|\
""", sender='Cabot/Service')
