from manage import OpenstackManage
from openstack_dummies import *
import logging
import threading
import compute
import requests
import socket
import time


class OpenstackApiEndpoint():
    """
    Base class for an OpenStack datacenter.
    It holds information about all connected endpoints.
    """
    dc_apis = []

    def __init__(self, listenip, port):
        self.ip = listenip
        self.port = port
        self.compute = compute.OpenstackCompute()
        self.openstack_endpoints = dict()
        self.openstack_endpoints['keystone'] = KeystoneDummyApi(self.ip, self.port)
        self.openstack_endpoints['neutron'] = NeutronDummyApi(self.ip, self.port + 4696, self.compute)
        self.openstack_endpoints['nova'] = NovaDummyApi(self.ip, self.port + 3774, self.compute)
        self.openstack_endpoints['heat'] = HeatDummyApi(self.ip, self.port + 3004, self.compute)
        self.openstack_endpoints['glance'] = GlanceDummyApi(self.ip, self.port + 4242, self.compute)

        self.rest_threads = list()
        self.manage = OpenstackManage()
        self.manage.add_endpoint(self)
        OpenstackApiEndpoint.dc_apis.append(self)

    def connect_datacenter(self, dc):
        """
        Connect a datacenter to this endpoint.
        An endpoint can only be connected to a single datacenter.

        :param dc: Datacenter object
        :type dc: :class:`dc`
        """
        self.compute.dc = dc
        for ep in self.openstack_endpoints.values():
            ep.manage = self.manage
        logging.info \
            ("Connected DC(%s) to API endpoint %s(%s:%d)" % (dc.label, self.__class__.__name__, self.ip, self.port))

    def connect_dc_network(self, dc_network):
        """
        Connect the datacenter network to the endpoint.

        :param dc_network: Datacenter network reference
        :type dc_network: :class:`.net`
        """
        self.manage.net = dc_network
        self.compute.nets[self.manage.floating_network.id] = self.manage.floating_network
        logging.info("Connected DCNetwork to API endpoint %s(%s:%d)" % (
            self.__class__.__name__, self.ip, self.port))

    def start(self, wait_for_port=False):
        """
        Start all connected OpenStack endpoints that are connected to this API endpoint.
        """
        for component in self.openstack_endpoints.values():
            component.compute = self.compute
            component.manage = self.manage
            thread = threading.Thread(target=component._start_flask, args=())
            thread.daemon = True
            thread.name = component.__class__
            thread.start()
            if wait_for_port:
                self._wait_for_port(component.ip, component.port)
                

    def stop(self):
        """
        Stop all connected OpenStack endpoints that are connected to this API endpoint.
        """
        for component in self.openstack_endpoints.values():
            url = "http://" + component.ip + ":" + str(component.port) + "/shutdown"
            try:
                requests.get(url)
            except:
                # seems to be stopped
                pass

    def _wait_for_port(self, ip, port):
        for i in range(0, 10):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)  # 1 Second Timeout
            r = s.connect_ex((ip, port))
            if r == 0:
                break  # port is open proceed
            else:
                logging.warning("Waiting for {}:{} ... ({}/10)".format(ip, port, i + 1))
            time.sleep(1)
