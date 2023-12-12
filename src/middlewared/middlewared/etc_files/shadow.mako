<%
    from datetime import datetime
    from middlewared.utils import filter_list

    def get_passwd(entry):
        if entry['password_disabled']:
            return "*"
        elif user['locked']:
            return "!"

        return entry['unixhash']

    def convert_to_days(value):
        ts = int(value.strftime('%s'))
        return int(ts / 86400)

    def parse_aging(entry):
        """
        <last change>:<min>:<max>:<warning>:<inactivity>:<expiration>:<reserved>
        """
        if not entry['password_aging_enabled']:
            outstr = ':::::'
            if user['account_expiration_date'] is not None:
                outstr += str(convert_to_days(user['account_expiration_date']))

            outstr += ':'
            return outstr

        outstr = ''
        if user['last_password_change'] is not None:
            outstr += str(convert_to_days(user['last_password_change']))
        if user['password_change_required']:
            outstr += '0'
        outstr += ':'

        for key in [
            'min_password_age',
            'max_password_age',
            'password_warn_period',
            'password_inactivity_period',
        ]:
            if user.get(key) is not None:
                outstr += str(user[key])

            outstr += ':'

        if user['account_expiration_date'] is not None:
            outstr += str(convert_to_days(user['account_expiration_date']))

        outstr += ':'
        return outstr

%>\
% for user in filter_list(render_ctx['user.query'], [], {'order_by': ['-builtin', 'uid']}):
${user['username']}:${get_passwd(user)}:${parse_aging(user)}
% endfor
% if render_ctx.get('cluster_healthy'):
% for user in filter_list(render_ctx['clustered_users'], [], {'order_by': ['uid']}):
${user['username']}:${'!' if user['locked'] else '*'}:18397:0:99999:7:::
% endfor
% endif
