import multiprocessing
import sys
from multiprocessing import Process

from utils.IPUtils import checkIP

# Set spawn method explicitly for Windows compatibility
if "win32" in sys.platform:
    multiprocessing.set_start_method('spawn', force=True)
else:
    multiprocessing.set_start_method('fork', force=True)

from Configuration import *
CosThetaConfigurator.getInstance()
from utils.CosThetaPrintUtils import *

def startTheWebServiceEndpoints():
    from endpoints.AutoCompanyWebService import startWebService
    startWebService()

def startTheMIService():
    from endpoints.AutoCompany_MI_Light import startMIServer
    startMIServer()

def startTheShowScreenService():
    from endpoints.ShowScreen import startTheShowScreenService
    startTheShowScreenService()

def threadToKeepProgramFromShuttingDown():
    while True:
        try:
            time.sleep(10)
            printBoldBlue(f"Services are alive")
        except:
            pass

def main():
    # global showSplash

    try:
        P1 = Process(target=startTheWebServiceEndpoints, args=())
        P1.start()
        time.sleep(3)
        printBoldBlue("Started the WebService Endpoints")
    except:
        printBoldRed("Could not start the WebService Endpoints")

    try:
        P2 = Process(target=startTheMIService, args=())
        P2.start()
        time.sleep(1)
        printBoldBlue("Started the MI Dashboard Service")
    except:
        printBoldRed("Could not start the MI Dashboard Service")

    try:
        P3 = Process(target=startTheShowScreenService, args=())
        P3.start()
        time.sleep(1)
        printBoldBlue("Started the Show Screen Service")
    except:
        printBoldRed("Could not start the Show Screen Service")

    keepAliveThread = threading.Thread(name="Stop Monitoring Thread", target=threadToKeepProgramFromShuttingDown,
                                            args=(),
                                            daemon=True)

    keepAliveThread.start()
    keepAliveThread.join()

if __name__ == '__main__':
    main()
    sys.exit(0)
