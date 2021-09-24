#
# PAM_WINBIND.CONF(5)		The configuration file for the PAM module for Winbind
# $FreeBSD$
#
<%
    """
    Options in PAM configuration files take precedence to those in the pam_winbind.conf.
    """
    ad = middleware.call_sync('activedirectory.config')
%>
[global]
%if ad['verbose_logging']:
debug = yes
%else:
silent = yes
%endif
