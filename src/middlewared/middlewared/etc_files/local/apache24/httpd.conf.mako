<%
    if IS_FREEBSD:
        module_path = "libexec/apache24"
    else:
        module_path = "/usr/lib/apache2/modules"
%>\
# Generating apache general httpd.conf
# The absolutely necessary modules
LoadModule authn_file_module ${module_path}/mod_authn_file.so
LoadModule authn_core_module ${module_path}/mod_authn_core.so
LoadModule authz_user_module ${module_path}/mod_authz_user.so
LoadModule authz_core_module ${module_path}/mod_authz_core.so
LoadModule alias_module ${module_path}/mod_alias.so
LoadModule mpm_prefork_module ${module_path}/mod_mpm_prefork.so
% if IS_FREEBSD:
LoadModule mpm_itk_module ${module_path}/mod_mpm_itk.so
LoadModule unixd_module ${module_path}/mod_unixd.so
% else:
LoadModule mpm_itk_module ${module_path}/mpm_itk.so
% endif
LoadModule auth_basic_module ${module_path}/mod_auth_basic.so
LoadModule auth_digest_module ${module_path}/mod_auth_digest.so
LoadModule setenvif_module ${module_path}/mod_setenvif.so
LoadModule dav_module ${module_path}/mod_dav.so
LoadModule dav_fs_module ${module_path}/mod_dav_fs.so
LoadModule allowmethods_module ${module_path}/mod_allowmethods.so
LoadModule ssl_module ${module_path}/mod_ssl.so
LoadModule socache_shmcb_module ${module_path}/mod_socache_shmcb.so

# The still deciding whether or not to keep thse modules or not
LoadModule authz_host_module ${module_path}/mod_authz_host.so
LoadModule authz_groupfile_module ${module_path}/mod_authz_groupfile.so
LoadModule access_compat_module ${module_path}/mod_access_compat.so
LoadModule reqtimeout_module ${module_path}/mod_reqtimeout.so
LoadModule filter_module ${module_path}/mod_filter.so
LoadModule mime_module ${module_path}/mod_mime.so
% if IS_FREEBSD:
LoadModule log_config_module ${module_path}/mod_log_config.so
% endif
LoadModule env_module ${module_path}/mod_env.so
LoadModule headers_module ${module_path}/mod_headers.so
#LoadModule version_module ${module_path}/mod_version.so
LoadModule status_module ${module_path}/mod_status.so
LoadModule autoindex_module ${module_path}/mod_autoindex.so
LoadModule dir_module ${module_path}/mod_dir.so

# Third party modules
% if IS_FREEBSD:
IncludeOptional etc/apache24/modules.d/[0-9][0-9][0-9]_*.conf
% endif
ServerName localhost

# Limiting the number of idle threads
# see: http://httpd.apache.org/docs/current/mod/prefork.html#MinSpareServers
<IfModule mpm_itk_module>
        StartServers 1
        MinSpareServers 1
</IfModule>

# I really do not know why mpm-prefork or mpm-event are needed
# to start apache24 successfully when I already have mpm itk
# (see: https://bugs.freenas.org/issues/14396)
# Bandaid fix, till I can (hopefully) think of a better fix
# Please fix if you can!
<IfModule mpm_prefork_module>
        StartServers 1
        MinSpareServers 1
</IfModule>

<IfModule unixd_module>
% if IS_FREEBSD:
User www
Group www
% else:
User www-data
Group www-data
% endif
</IfModule>

<IfModule dir_module>
    DirectoryIndex disabled
</IfModule>

<Files ".ht*">
    Require all denied
</Files>

ErrorLog "/var/log/httpd-error.log"
LogLevel warn

<IfModule log_config_module>
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
    LogFormat "%h %l %u %t \"%r\" %>s %b" common
    <IfModule logio_module>
      LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %I %O" combinedio
    </IfModule>
    CustomLog "/var/log/httpd-access.log" common

</IfModule>

<IfModule alias_module>
    ScriptAlias /cgi-bin/ "/usr/local/www/apache24/cgi-bin/"
</IfModule>

<IfModule mime_module>
    #
    # TypesConfig points to the file containing the list of mappings from
    # filename extension to MIME-type.
    #
    % if IS_FREEBSD:
    TypesConfig etc/apache24/mime.types
    % else:
    TypesConfig /etc/mime.types
    % endif

    #
    # AddType allows you to add to or override the MIME configuration
    # file specified in TypesConfig for specific file types.
    #
    #AddType application/x-gzip .tgz
    #
    # AddEncoding allows you to have certain browsers uncompress
    # information on the fly. Note: Not all browsers support this.
    #
    #AddEncoding x-compress .Z
    #AddEncoding x-gzip .gz .tgz
    #
    # If the AddEncoding directives above are commented-out, then you
    # probably should define those extensions to indicate media types:
    #
    AddType application/x-compress .Z
    AddType application/x-gzip .gz .tgz

    #
    # AddHandler allows you to map certain file extensions to "handlers":
    # actions unrelated to filetype. These can be either built into the server
    # or added with the Action directive (see below)
    #
    # To use CGI scripts outside of ScriptAliased directories:
    # (You will also need to add "ExecCGI" to the "Options" directive.)
    #
    #AddHandler cgi-script .cgi

    # For type maps (negotiated resources):
    #AddHandler type-map var

    #
    # Filters allow you to process content before it is sent to the client.
    #
    # To parse .shtml files for server-side includes (SSI):
    # (You will also need to add "Includes" to the "Options" directive.)
    #
    #AddType text/html .shtml
    #AddOutputFilter INCLUDES .shtml
</IfModule>

# Secure (SSL/TLS) connections
#Include etc/apache24/extra/httpd-ssl.conf
#
# Note: The following must must be present to support
#       starting without SSL on platforms with no /dev/random equivalent
#       but a statically compiled-in mod_ssl.
#
<IfModule ssl_module>
SSLRandomSeed startup builtin
SSLRandomSeed connect builtin
SSLProtocol +TLSv1 +TLSv1.1 +TLSv1.2
</IfModule>

% if IS_FREEBSD:
Include etc/apache24/Includes/*.conf
% else:
Include Includes/*.conf
% endif
