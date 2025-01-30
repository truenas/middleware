from middlewared.utils.auditd import set_audit_rules


def render(service, middleware, render_ctx):
    set_audit_rules(
        render_ctx['system.security.config']['enable_gpos_stig'],
        render_ctx['system.product_type']['truenas_product_type']
    )
