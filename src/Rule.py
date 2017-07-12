from ipaddress import *
from scapy.all import *

from Utils import *
from Action import *
from Protocol import *
from IPNetwork import *
from Ports import *
from PrintPacket import *

class Rule:
    """A NIDS rule."""

    def __init__(self, str):
        """Construct a rule from a string."""

        self.string = str

        str = str.strip()
        strs = str.split(' ')

        if (len(strs) >= 7):
            # action
            if (strs[0] == "alert"):
                self.action = Action.ALERT
            else:
                raise ValueError("Invalid rule : incorrect action : '" + strs[0] + "'.")

            # protocol
            protocol = 0
            if (strs[1] == "tcp"):
                self.protocol = Protocol.TCP
            elif (strs[1] == "udp"):
                self.protocol = Protocol.UDP
            elif (strs[1] == "http"):
                self.protocol = Protocol.HTTP
            else:
                raise ValueError("Invalid rule : incorrect protocol : '" + strs[1] + "'.")

            # source ip and ports
            try:
                self.srcIps = IPNetwork(strs[2])
            except:
                raise ValueError("Invalid rule : incorrect source ips : '" + strs[2] + "'.")
            try:
                self.srcPorts = Ports(strs[3])
            except:
                raise ValueError("Invalid rule : incorrect source ports : '" + strs[3] + "'.")

            # destination ip and ports
            try:
                self.dstIps = IPNetwork(strs[5])
            except:
                raise ValueError("Invalid rule : incorrect destination ips : '" + strs[5] + "'.")

            try:
                self.dstPorts = Ports(strs[6])
            except:
                raise ValueError("Invalid rule : incorrect destination ports : '" + strs[6] + "'.")

            # Options
            strs = str.split('(')
            if (len(strs) >= 2):
                # options may be present
                opts = strs[1].split(';')
                for opt in opts:
                    kv = opt.split(':',1)
                    if (len(kv) >= 2):
                        option = kv[0].strip()
                        value = kv[1].strip()

                        if (option == "msg"):
                            self.msg = value
                        elif (option == "tos"):
                            self.tos = int(value)
                        elif (option == "len"):
                            self.len = int(value)
                        elif (option == "offset"):
                            self.offset = int(value)
                        elif (option == "seq"):
                            self.seq = int(value)
                        elif (option == "ack"):
                            self.ack = int(value)
                        elif (option == "flags"):
                            self.flags = value
                        elif (option == "http_request"):
                            self.http_request = value
                            # remove starting and ending ["]
                            if (self.http_request.endswith('"')):
                                self.http_request = self.http_request[:-1]
                            if (self.http_request.startswith('"')):
                                self.http_request = self.http_request[1:]
                        elif (option == "content"):
                            self.content = value;
                            # remove starting and ending ["]
                            if (self.content.endswith('"')):
                                self.content = self.content[:-1]
                            if (self.content.startswith('"')):
                                self.content = self.content[1:]
                        else:
                            raise ValueError("Invalid rule : incorrect option : '" + option + "'.")
            # Done
        else:
            raise ValueError("Invalid rule : a rule must include mandatory elements : action protocol src_ips src_ports -> dst_ips dst_ports")

    def __repr__(self):
        """Returns the string representing the Rule"""
        # simply use initialization string
        return self.string

    def match(self, pkt):
        """
        Returns True if and only if the rule is matched by given packet,
        i.e. if every part of the rule is met by the packet.
        """
        # check protocol
        if (not self.checkProtocol(pkt)):
            return False

        # check IP source and destination
        if (not self.checkIps(pkt)):
            return False

        # check source Port
        if (not self.checkPorts(pkt)):
            return False

        # check options
        if (not self.checkOptions(pkt)):
            return False

        # otherwise the rule is met
        return True

    def checkProtocol(self, pkt):
        """ Returns True if and only if the rule concerns packet's protocol """
        f = False
        if (self.protocol == Protocol.TCP and TCP in pkt):
            f = True
        elif (self.protocol == Protocol.UDP and UDP in pkt):
            f = True
        elif (self.protocol == Protocol.HTTP and TCP in pkt):
            # HTTP packet has to be TCP
            # check payload to determine if this is a HTTP packet
            if (isHTTP(pkt)):
                f = True
        return f

    def checkIps(self, pkt):
        """Returns True if and only if the rule's IPs concern the pkt IPs"""
        f = False
        if (IP not in pkt):
            f = False
        else:
            srcIp = pkt[IP].src
            dstIp = pkt[IP].dst
            ipSrc = ip_address(unicode(srcIp))
            ipDst = ip_address(unicode(dstIp))
            if (self.srcIps.contains(ipSrc) and self.dstIps.contains(ipDst)):
                # ipSrc and ipDst match rule's source and destination ips
                f = True
            else:
                f = False
        return f

    def checkPorts(self, pkt):
        """Returns True if and only if the rule's Ports concern packet's Ports"""
        f = False
        if (UDP in pkt):
            srcPort = pkt[UDP].sport
            dstPort = pkt[UDP].dport
            if (self.srcPorts.contains(srcPort) and self.dstPorts.contains(dstPort)):
                f = True
        elif (TCP in pkt):
            srcPort = pkt[TCP].sport
            dstPort = pkt[TCP].dport
            if (self.srcPorts.contains(srcPort) and self.dstPorts.contains(dstPort)):
                f = True
        return f

    def checkOptions(self, pkt):
        """ Return True if and only if all options are matched """

        # TODO : change hasattr to try except
        try:
            if (IP in pkt):
                if (self.tos != int(pkt[IP].tos)):
                    return False
            else:
                return False
        except AttributeError:
            pass

        try:
            if (IP in pkt):
                if (self.len != int(pkt[IP].ihl)):
                    return False
            else:
                return False
        except AttributeError:
            pass

        try:
            if (IP in pkt):
                if (self.offset != int(pkt[IP].frag)):
                    return False
            else:
                return False
        except AttributeError:
            pass

        try:
            if (TCP not in pkt):
                return False
            else:
                if (self.seq != int(pkt[TCP].seq)):
                    return False
        except AttributeError:
            pass

        try:
            if (TCP not in pkt):
                return False
            else:
                if (self.ack != int(pkt[TCP].ack)):
                    return False
        except AttributeError:
            pass

        try:
            # match if and only if the received packet has all the rule flags set
            if (TCP not in pkt):
                return False
            else:
                for c in self.flags:
                    pktFlags = pkt[TCP].underlayer.sprintf("%TCP.flags%")
                    if (c not in pktFlags):
                        return False
        except AttributeError:
            pass


        try:
            if (not isHTTP(pkt)):
                return False
            elif (TCP in pkt and pkt[TCP].payload):
                data = str(pkt[TCP].payload)
                words = data.split(' ')
                if ((len(words) < 1) or (words[0].rstrip() !=  self.http_request)):
                    return False
            else:
                return False
        except AttributeError:
            pass

        try:
            payload = None
            if (TCP in pkt):
                payload = pkt[TCP].payload
            elif (UDP in pkt):
                payload = pkt[UDP].payload
            if (payload):
                if (self.content not in str(payload)):
                    return False
            else:
                return False
        except AttributeError:
            pass

        return True
