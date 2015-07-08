# $FreeBSD: src/etc/root/dot.profile,v 1.21 2007/05/29 06:33:10 dougb Exp $
#
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin:~/bin:/usr/local/fusion-io
export PATH
HOME=/root; export HOME
TERM=${TERM:-cons25}; export TERM
PAGER=more; export PAGER

# set ENV to a file invoked each time sh is started for interactive use.
ENV=$HOME/.shrc; export ENV

# History file since / is read-only (see #4776)
HISTFILE=/tmp/.hist$$

#set -o vi
set -o emacs
if [ `id -u` = 0 ]; then
    PS1="`hostname -s`# "
else
    PS1="`hostname -s`% "
fi
