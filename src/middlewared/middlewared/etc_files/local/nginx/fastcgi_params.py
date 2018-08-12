import re


def file_action(mode, data=None):
    with open('/usr/local/etc/nginx/fastcgi_params', mode) as file:
        if mode == 'r':
            return file.read()
        elif mode in ('a', 'w'):
            file.write(data)


async def render(service, middleware):
    general_settings = await middleware.call('system.general.config')

    content = file_action('r')
    match = re.search('fastcgi_param(\s+)HTTPS(\s+)on;\n', content)
    if general_settings['ui_httpsredirect']:
        if not match:
            file_action('a', 'fastcgi_param HTTPS on;\n')
    else:
        if match:
            file_action(
                'w',
                re.sub('fastcgi_param(\s+)HTTPS(\s+)on;\n', '', content)
            )
