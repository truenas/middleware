import yaml

from middlewared.service import Service, ValidationErrors


class AppCustomService(Service):

    class Config:
        namespace = 'app.custom'
        private = True

    def create(self, data, job=None):
        """
        Create a custom app.
        """
        verrors = ValidationErrors()
        compose_keys = ('custom_compose_config', 'custom_compose_config_string')
        if all(not data.get(k) for k in compose_keys):
            verrors.add('app_create.custom_compose_config', 'This field is required')
        elif all(data.get(k) for k in compose_keys):
            verrors.add('app_create.custom_compose_config_string', 'Only one of these fields should be provided')

        compose_config = data.get('custom_compose_config')
        if data.get('custom_compose_config_string'):
            try:
                compose_config = yaml.YAMLError(data['custom_compose_config_string'])
            except yaml.YAMLError:
                verrors.add('app_create.custom_compose_config_string', 'Invalid YAML provided')

        verrors.check()

        # For debug purposes
        job = job or type('dummy_job', (object,), {'set_progress': lambda *args: None})()
        job.set_progress(25, 'Initial validation completed for custom app creation')

        app_name = data['app_name']
        compose_contents = data['custom_compose']
