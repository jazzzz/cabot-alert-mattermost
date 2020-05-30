from os import environ as env
import requests
import json

from django.db import models
from django.conf import settings
from django.template import Context, Template

from cabot.cabotapp.alert import AlertPlugin, AlertPluginUserData
from cabot.cabotapp.models import Service

EMOJIS = {
    Service.PASSING_STATUS: ":ok_hand:",
    Service.WARNING_STATUS: ":warning:",
    Service.ERROR_STATUS: ":rotating_light:",
    Service.CRITICAL_STATUS: ":fire:",
}

text_template = """\
{% if service.overall_status == service.PASSING_STATUS %}\
[Service {{ service.name }}]({{ scheme }}://{{ host }}{% url 'service' pk=service.id %}) is back to normal\
{% else %}\
**[Service {{ service.name }}]({{ scheme }}://{{ host }}{% url 'service' pk=service.id %}) is reporting {{ service.overall_status }} status**\
{% endif %}\
 {{ emoji }}

{% if alert %}{% for alias in users %} @{{ alias }}{% endfor %}{% endif %}\
{% if service.overall_status != service.PASSING_STATUS %}

| Check | Error |
|:------|:------|\
{% for check in service.all_failing_checks %}
| {{ check.name }} |\
    {% if check.check_category == 'Jenkins check' %}\
        {% if check.last_result.error %}\
[{{ check.last_result.error|safe }}]({{check.jenkins_config.jenkins_api}}job/{{ check.name }}/{{ check.last_result.job_number }}/console)\
        {% else %}\
{{check.jenkins_config.jenkins_api}}/job/{{ check.name }}/{{check.last_result.job_number}}/console\
        {% endif %}\
    {% else %}\
{% if check.last_result.error %} {{ check.last_result.error|safe }} {% endif %}\
    {% endif %}\
|\
{% endfor %}\
{% endif %}\
"""

# This provides the mattermost alias for each user. Each object corresponds to a User
class MattermostAlert(AlertPlugin):
    name = "Mattermost"
    author = "Jazz"

    def send_alert(self, service, users, duty_officers):
        alert = True
        users = list(users) + list(duty_officers)
        mattermost_aliases = [u.mattermost_alias for u in MattermostAlertUserData.objects.filter(user__user__in=users)]

        if service.overall_status == service.WARNING_STATUS:
            alert = False  # Don't alert at all for WARNING
        if service.overall_status == service.ERROR_STATUS:
            if service.old_overall_status == service.ERROR_STATUS:
                alert = False  # Don't alert repeatedly for ERROR
        if service.overall_status == service.PASSING_STATUS:
            if service.old_overall_status == service.WARNING_STATUS:
                alert = False  # Don't alert for recovery from WARNING status

        c = Context({
            'service': service,
            'users': mattermost_aliases,
            'host': settings.WWW_HTTP_HOST,
            'scheme': settings.WWW_SCHEME,
            'emoji': EMOJIS.get(service.overall_status),
            'alert': alert,
        })
        message = Template(text_template).render(c)
        self._send_mattermost_alert(message, sender='Cabot/%s' % service.name)

    def _send_mattermost_alert(self, message, sender='Cabot'):

        channel = env.get('MATTERMOST_ALERT_CHANNEL')
        url = env.get('MATTERMOST_WEBHOOK_URL')
        icon_url = env.get('MATTERMOST_ICON_URL')

        resp = requests.post(url, json={
            'text': message,
            'channel': channel,
            'username': sender,
            'icon_url': icon_url,
        })

class MattermostAlertUserData(AlertPluginUserData):
    name = "Mattermost Plugin"
    mattermost_alias = models.CharField(max_length=50, blank=True)

    def serialize(self):
        return {
            "mattermost_alias": self.mattermost_alias
        }
