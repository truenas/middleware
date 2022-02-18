if (( ${+WEB_CLIENT} )); then
	screen -xRR WebShell
fi

if [ -f /usr/local/sbin/hactl ]; then
	/usr/local/sbin/hactl status -q
fi

cat ~/.warning
