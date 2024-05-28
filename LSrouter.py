import sys
from collections import defaultdict
from router import Router
from packet import Packet
from json import dumps, loads
import dijkstar

class LSrouter(Router):
    """Link state routing protocol implementation."""

    def __init__(self, addr, heartbeatTime):
        Router.__init__(self, addr)  # initialize superclass - don't remove
        self.heartbeatTime = heartbeatTime
        self.last_time = 0
        # Hints: initialize local state
        # pass
        
        self.graph = dijkstar.Graph(undirected = True)
        self.graph.add_node(self.addr)
        self.preceding_no = {}
        self.previous_LS = {}
        self.updated_LS = {}
        self.LS_db = {}
        self.local_state = {}
        self.forwarding_table = {}
        # self.updated_seq_no = 0
        self.sequence_no = 0
        

    def handlePacket(self, port, packet):
        if packet.isTraceroute():
            self.handleTraceroute(packet) #helper function to handle traceroute
        else:
            source_no, content = loads(packet.content)
            content = dict(content)
            self.preceding_no.setdefault(packet.srcAddr, 0)

            updated_LS = content != self.previous_LS.get(packet.srcAddr)
            self.previous_LS[packet.srcAddr] = content

            if source_no > self.preceding_no.get(packet.srcAddr, 0) and updated_LS:
                self.preceding_no[packet.srcAddr] = source_no

                self.forwarding_table.update({addr: None for addr in content if addr not in self.forwarding_table and addr != self.addr})

                if packet.srcAddr in self.graph.get_data():
                    self.graph.remove_node(packet.srcAddr)

                self.updateGraph(packet, content)

                self.updateRoutingTable()

                self.broadcastExceptSource(packet, source_no, content)

    def handleNewLink(self, port, endpoint, cost):
        self.local_state[endpoint] = (port, cost)
        self.graph.add_node(endpoint)
        self.graph.add_edge(self.addr, endpoint, cost)
        self.forwarding_table[endpoint] = endpoint

        dest_addr_list = list(self.forwarding_table.keys())
        i = 0
        while i < len(dest_addr_list):
            dest_addr = dest_addr_list[i]
            self.forwarding_table[dest_addr] = dijkstar.find_path(self.graph, self.addr, dest_addr).nodes[1]
            i += 1
        # sequence_no_updated+=1 ->? not here
        self.updateLS()

    def handleRemoveLink(self, port):
        remove_link = next((addr for addr, ls_temp in self.local_state.items() if ls_temp[0] == port), None)
        remove_flag = remove_link
        if remove_flag:
            self.local_state.pop(remove_link)

        self.graph.remove_edge(self.addr, remove_link)

        dest_addr_list = list(self.forwarding_table.keys())
        i = 0
        while i < len(dest_addr_list):
            dest_addr = dest_addr_list[i]
            try:
                self.forwarding_table[dest_addr] = dijkstar.find_path(self.graph, self.addr, dest_addr).nodes[1]
            except:
                self.forwarding_table[dest_addr] = None
            i += 1

        self.updateLS()

    def handleTime(self, timeMillisecs):
        if timeMillisecs - self.last_time >= self.heartbeatTime:
            self.last_time = timeMillisecs
        # sequence_no_updated+=
            self.updateLS() #simply re-broadcast the state after set time

    def debugString(self):
        pass #not implemented/needed

    def handleTraceroute(self, packet):
        if (nxt_add := self.forwarding_table.get(packet.dstAddr)) is not None:
            nxt_port, _ = self.local_state[nxt_add]
            self.send(nxt_port, packet)

    def updateLS(self):
        self.sequence_no += 1
        content = dumps((self.sequence_no, self.local_state))
        local_state_items = list(self.local_state.items())
        i = 0
        while i < len(local_state_items):
            dest_addr, (dest_port, _) = local_state_items[i]
            self.send(dest_port, Packet('ROUTING', self.addr, dest_addr, content))
            i += 1


    def updateRoutingTable(self):
        dest_addr_list = list(self.forwarding_table.keys())
        i = 0
        while i < len(dest_addr_list):
            dest_addr = dest_addr_list[i]
            try:
                path = dijkstar.find_path(self.graph, self.addr, dest_addr)
                self.forwarding_table[dest_addr] = path.nodes[1] if path.nodes[1] in self.local_state else None
            except:
                self.forwarding_table[dest_addr] = None
            i += 1

    def updateGraph(self, packet, content):
        self.graph.add_node(packet.srcAddr)
        content_items = list(content.items())
        i = 0
        while i < len(content_items):
            addr, c = content_items[i]
            self.graph.add_node(addr)
            self.graph.add_edge(packet.srcAddr, addr, c[1])
            i += 1

    def broadcastExceptSource(self, packet, source_no, content):
        for dest_addr in self.local_state:
            if dest_addr not in {self.addr, packet.srcAddr}:
                dest_port, _ = self.local_state[dest_addr]
                self.send(dest_port, Packet('ROUTING', packet.srcAddr, packet.dstAddr, dumps((source_no, content))))

        self.updateLS()
        self.previous_LS[packet.srcAddr] = content
