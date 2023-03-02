class iSNSPException(Exception):
    """
    Base exception for our iSNSP functions
    """


class MalformedPacketError(iSNSPException):
    """
    The iSNSP packet has some sort of issue
    """
