#!/usr/local/bin/bash
# Jim Lofft 06/19/2009
# find_alias_for_msmtp.sh
# popper email server was replaced by exchange. I replaced sendmail with this script 
# which scans /etc/alias file for a valid domain email address and calls msmtp (http://msmtp.sourceforge.net/)
#
# changed a little by Ovidiu Constantin <ovidiu@mybox.ro> && http://blog.mybox.ro/
#
# Sanitized for a BSD system by Josh Paetzel <jpaetzel@FreeBSD.org>

DEFAULTEMAIL="you@domain.com"

v_recipient=0
v_msg=`cat`       # email message contents
MSMTP=`which msmtp || echo "/usr/local/bin/msmtp"`

if [  "$1" = '-i'  ] ; then
   # mailx calls sendmail with -i as the 1st param and the recipient as the second param
   v_recipient=$2
elif [ "$1" = '-t' ] ; then
    # most other programs call sendmail with a -t option
    v_to=`echo "$v_msg" | grep -m 1 'To: '`
    v_recipient=${v_to:4:50}
else
   # no parameter, sendmail was called with the recipient as parameter
   v_recipient=$1
fi

if [ -n "${v_recipient}" ] ; then

    # trim spaces from recipient email address
    v_recipient="${v_recipient// /}"

    # see if this email is to a @ domain.com
    v_domain=`echo ${v_recipient} | grep -o "@[[:alnum:][:graph:]]" | sed s/@//`

    # if this email isn't to a domain, then it's a local email, so
    # look up the recipient in the aliases file

        if [ -z "$v_domain"  ]; then
            # grep alias file
            v_find_alias=`grep -E ^${v_recipient}: /etc/aliases | awk '{print $2}'`
            v_alias_domain=`echo ${v_find_alias} | grep -o "@[[:alnum:][:graph:]]"`
                if [ -z "$v_alias_domain" ]; then
                    # we didn't find an @, grep alias again
                    v_next_alias=`grep "$v_find_alias": /etc/aliases | awk '{print $2}'`
                    v_alias_domain=`echo ${v_find_alias} | grep -o "@[[:alnum:][:graph:]]"`
                    if [ -z "$v_alias_domain" ]; then
                        # email someone important if no @ alias is found
                        v_recipient=$DEFAULTEMAIL
                    else
                        v_recipient=$v_next_alias
                    fi
                else
                    v_recipient=$v_find_alias
                fi
        fi
    # Send msmtp email
    echo "$v_msg" | $MSMTP -i $v_recipient
else
    # we're not sure who this email is for, just send it to msmtp and see what happens..
    echo "$v_msg" | $MSMTP $1 $2 $3 $4 $5
fi
