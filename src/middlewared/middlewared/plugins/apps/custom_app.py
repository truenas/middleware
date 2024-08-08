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
        if not data.get('custom_compose_config'):
            verrors.add('app_create.custom_compose_config', 'This field is required')

        verrors.check()

        # For debug purposes
        job = job or type('dummy_job', (object,), {'set_progress': lambda *args: None})()
        job.set_progress(25, 'Initial validation completed for custom app creation')

        app_name = data['app_name']
        compose_contents = data['custom_compose']
