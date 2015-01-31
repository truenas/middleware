import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including CIFS, NFS, and AFP in Sharing (yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Sharing test suite!'
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

import sharing_cifs                                                                                                       
import sharing_nfs                                                                                                      
import sharing_afp


print '***Running Sharing_CIFS ......'
sharing_cifs.put()
sharing_cifs.delete()
print ''

#print '***Running Sharing_NFS ......'
#sharing_nfs.put()
#sharing_nfs.delete()
#print ''

print '***Running Sharing_AFP ......'
sharing_afp.put()
sharing_afp.delete()
print '\n'
