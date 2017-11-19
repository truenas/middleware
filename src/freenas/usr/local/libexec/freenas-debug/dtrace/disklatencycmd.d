#!/usr/sbin/dtrace -s

#pragma D option quiet

/* from http://www.mail-archive.com/dtrace-discuss@opensolaris.org/msg03755.html */
#pragma D option aggsize=8m
#pragma D option bufsize=16m
#pragma D option dynvarsize=32m
/*
#pragma D option aggrate=0
#pragma D option cleanrate=50Hz
*/


dtrace:::BEGIN
{
	dstart = timestamp;
}

profile:::tick-1sec
/i++ >= 20/
{
   exit(0);
}

/*arg0 is struct buffer, arg1 is devt_t  arg2 is fileinfo_t */

io:::start
/*filter out devices that shouldn't beak */
/ (args[1]->device_name != 0) &&  (args[1]->unit_number >= 0) /
{
	start_time[arg0] = timestamp;
}

io:::done
/(this->start = start_time[arg0]) && (start_time[arg0] > 0) && (args[1]->unit_number >= 0 ) /
{
	this->delta = (timestamp - this->start) / 1000;
	@q[args[1]->device_name, args[1]->unit_number] =
	    quantize(this->delta);
	@max[args[1]->device_name, args[1]->unit_number] = max(this->delta);
	@avg[args[1]->device_name, args[1]->unit_number] = avg(this->delta);
	start_time[arg0] = 0;
}

dtrace:::END
{
	printf("total time, us: %d\n", (timestamp - dstart) / 1000);
	printa("   %s (%d), us:\n%@d\n", @q);
	printa("max%s (%d), us: %@d\n", @max);
	printa("avg%s (%d), us: %@d\n", @avg);
}
