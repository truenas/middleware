get_unique_jailname()
{
	# Poudriere takes a jail name, and a ports tree name,
	# and concatenates then creates a unique jail name
	# with: jail -c "${JAILNAME}-${PORTSTREENAME}".

	# Let's try to see with the jls command if anyone is already
	# using that unique jail name.  If so, let's try to generate another name.
 
	# Trick for iterating through alphabet obtained from
	# http://stackoverflow.com/questions/5999662/shellscript-iterate-through-letters
	local a=$(printf %d "'a")
	local z=$(printf %d "'z")
	local i=$a
	local available_jailname=""

	while [ $i -le $z ]; do
		c=$(printf \\$(printf %o $i))
		jls -n -q -j "j${c}-p" > /dev/null 2>&1
		if [ $? -ne 0 ]; then
			# jls failed, so j${c}-p is available.  Let's try it.
			available_jailname="j$c"
			break
		fi
		i=$(($i+1))
	done

	echo "$available_jailname"
}
