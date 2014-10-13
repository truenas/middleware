# $FreeBSD: head/etc/csh.cshrc 50472 1999-08-27 23:37:10Z peter $
#
# System-wide .cshrc file for csh(1).

set path = ( ~/bin /bin /usr/local/bin /usr/local/sbin /usr/bin /sbin \
             /usr/sbin )

set autocorrect
set autolist = ambiguous
set cdpath = ( ~ )
set complete = enhance
set correct = cmd
set filec

switch ($TERM)
    case "xterm*":
	set prompt = '%{\033]0;%n@%m:%~\007%}[%B%n@%m%b] %B%~%b%# '
       	breaksw
    default:
	set prompt = '[%B%n@%m%b] %B%~%b%# '
       	breaksw
endsw

set history = 500
unset autologout
unset noglob

setenv PAGER		"less"
setenv LSCOLORS ExGxFxdxCxegedabagExEx 

if (! $?term) exit

alias	ls		'ls -GFa'

set noglob
complete {alias,unalias}	p/1/a/
complete {bg,fg,stop}	c/%/j/ p/1/"(%)"//
complete cd		p/1/d/
complete chgrp		c/-/"(c f h R v -)"/ n/-/g/ p/1/g/ n/*/f/
complete chown		c/-/"(c f h R v -)"/ C@[./\$~]@f@ c/*[.:]/g/ \
			n/-/u/. p/1/u/. n/*/f/
complete exec		p/1/c/
complete kill		'c/-/S/' 'c/%/j/' \
			'n/*/`ps -xu $LOGNAME | awk '"'"'{print $2}'"'"'`/'
complete {killall,pkill}	c/-/S/ n/*/c/
complete rmdir		n/*/d/
complete set		'c/*=/f/' 'p/1/s/=' 'n/=/f/'
complete sysctl		'n/*/`sysctl -Na`/'
complete unset		n/*/s/
complete which		n/*/c/
unset noglob

bindkey -k up history-search-backward
bindkey -k down history-search-forward
bindkey "^W" backward-delete-word

#Bind Delete, Home, End and Insert keys
if ($?tcsh && $?prompt) then
bindkey "\e[1~" beginning-of-line # Home
bindkey "\e[7~" beginning-of-line # Home rxvt
bindkey "\e[2~" overwrite-mode # Ins
bindkey "\e[3~" delete-char # Delete
bindkey "\e[4~" end-of-line # End
bindkey "\e[8~" end-of-line # End rxvt
endif
