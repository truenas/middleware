if ( -f /usr/local/sbin/hactl) then
        /usr/local/sbin/hactl status -q
endif

echo
echo "Warning: settings changed through the CLI are not written to"
echo "the configuration database and will be reset on reboot."
echo
