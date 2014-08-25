import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including Volumes, Datasets, and snapshot etc... in Storage (yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Storage test suite!'
      sys.exit(0)
    if warn == 'no' or warn == 'n':
      sys.exit(0)
    elif warn == 'yes' or warn == 'y':
      break
    elif warn !='no' and warn != 'yes' and warn != 'y' and warn !='n':
      warn = raw_input("Invalid operation! Please input 'yes' or 'no':")
      oper_flag = oper_flag + 1
      continue

if __name__ == '__main__':
  main()

import storage_datasets
import storage_disk
import storage_scrub
import storage_snapshot
import storage_task
import storage_volume


print '\n***Running Storage-Volume ......'
storage_volume.delete()
storage_volume.post()
print ''

print '***Running Storage-Datasets ......'
storage_datasets.post()
storage_datasets.delete()
print ''

print '***Running Storage-Disk ......'
storage_disk.put()
print ''

print '***Running Storage-Task ......'
storage_task.delete()
storage_task.put()
print ''

print '***Running Storage-Scrub ......'
storage_scrub.put()
storage_scrub.delete()
print ''

print '***Running Storage-Snapshot ......'
storage_snapshot.post()
storage_snapshot.delete()
print ''

print '***Running Storage-Replication ......'
import storage_replication
storage_replication.put()
storage_replication.delete()
print ''
