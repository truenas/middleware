import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including Cronjob, Initshutdown, Rsync and Smarttest in Tasks(yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Task test suite!'
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

import tasks_cronjob
import tasks_initshutdown
import tasks_rsync
import tasks_smarttest

print '\n***Running Tasks-Crongjob ......'
tasks_cronjob.run()
tasks_cronjob.put()
print ''

print '***Running Tasks-Initshutdown ......'
tasks_initshutdown.put()
tasks_initshutdown.delete()
print ''

print '***Running Tasks-Rsync ......'
tasks_rsync.run() 
tasks_rsync.put() 
print ''

print '***Running Tasks-Smarttest ......'
tasks_smarttest.put()
tasks_smarttest.delete()
print ''
