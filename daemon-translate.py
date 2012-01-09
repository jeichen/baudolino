import sys, os
sys.path.append(os.path.sep.join(["","Library","Python","2.5","site-packages"]))

from  daemon import daemon
from lockfile.pidlockfile import PIDLockFile
import signal
import getopt

import translate 

def main():
    if len(sys.argv) < 2:
        print sys.argv[0] + " start|stop|restart "
        sys.exit(1)
    cmd = sys.argv[1]
    context = daemon.DaemonContext(pidfile=PIDLockFile('/tmp/translate.pid'), 
                                   working_directory='/tmp')
    
    if cmd == "start":
        with context:
            translate.main()
            
    elif cmd == "stop":
        context.close()
        
    elif cmd == "restart":
        print "todo: implement"

    else:
        print "start, stop, restart"
 

if __name__ == "__main__":
    main()
