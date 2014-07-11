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

io:::start
{
	start_time[arg0] = timestamp;
}

io:::done
/this->start = start_time[arg0]/
{
	this->delta = (timestamp - this->start) / 1000;
	@q[args[1]->device_name, args[1]->unit_number] =
	    lquantize(this->delta, 1000, 20000, 1000);
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
