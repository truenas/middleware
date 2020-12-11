<%
    import os

    def setup_skel():
        if not os.path.islink('/etc/skel'):
            try:
                if os.path.isdir('/etc/skel'):
                    os.rmdir('/etc/skel')
                os.symlink('/usr/share/skel', '/etc/skel')
            except Exception:
                middleware.logger.warning("Failed to set up skel directory "
                                          "automatically generated home directories "
                                          "for SSH users may be impacted.", exc_info=True)
%>
%if IS_FREEBSD:
${setup_skel()}
%endif
