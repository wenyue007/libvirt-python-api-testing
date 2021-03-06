#!/usr/bin/env python
# Test hotplug domain CPU, loop increase cpu to max then decrease
# to min

import time
import commands
from xml.dom import minidom

import libvirt
from libvirt import libvirtError

from src import sharedmod
from utils import utils

required_params = ('guestname', 'vcpu', 'username', 'password')
optional_params = {}


def check_domain_running(conn, guestname):
    """ check if the domain exists, may or may not be active """
    guest_names = []
    ids = conn.listDomainsID()
    for id in ids:
        obj = conn.lookupByID(id)
        guest_names.append(obj.name())

    if guestname not in guest_names:
        logger.error("%s doesn't exist or not running" % guestname)
        return 1
    else:
        return 0


def redefine_vcpu_number(domobj, guestname, vcpu):
    """dump domain xml description to change the vcpu number,
       then, define the domain again
    """
    guestxml = domobj.XMLDesc(0)
    logger.debug('''original guest %s xml :\n%s''' % (guestname, guestxml))

    doc = minidom.parseString(guestxml)

    newvcpu = doc.createElement('vcpu')
    newvcpuval = doc.createTextNode(str(vcpu))
    newvcpu.appendChild(newvcpuval)
    newvcpu.setAttribute('current', '1')

    domain = doc.getElementsByTagName('domain')[0]
    oldvcpu = doc.getElementsByTagName('vcpu')[0]

    domain.replaceChild(newvcpu, oldvcpu)

    return doc.toxml()


def check_current_vcpu(domobj, username, password):
    """dump domain xml description to get current vcpu number
    """
    guestxml = domobj.XMLDesc(1)
    logger.debug("domain %s xml is :\n%s" % (domobj.name(), guestxml))

    xml = minidom.parseString(guestxml)
    vcpu = xml.getElementsByTagName('vcpu')[0]
    if vcpu.hasAttribute('current'):
        attr = vcpu.getAttributeNode('current')
        current_vcpu = int(attr.nodeValue)
    else:
        logger.info("domain did not have 'current' attribute in vcpu element")
        current_vcpu = int(vcpu.childNodes[0].data)

    logger.info("check cpu number in domain")
    ip = utils.mac_to_ip(mac, 180)

    cmd = "cat /proc/cpuinfo | grep processor | wc -l"
    ret, output = utils.remote_exec_pexpect(ip, username, password, cmd)
    if not ret:
        logger.info("cpu number in domain is %s" % output)
        if int(output) == current_vcpu:
            logger.info("cpu number in domain is equal to current vcpu value")
            return current_vcpu
        else:
            logger.error("current vcpu is not equal as check in domain")
            return False
    else:
        logger.error("check in domain fail")
        return False


def set_vcpus(domobj, guestname, vcpu, username, password):
    """set the value of virtual machine to vcpu offline , then boot up
       the virtual machine
    """
    timeout = 60
    logger.info('destroy domain')

    try:
        domobj.destroy()
    except libvirtError as e:
        logger.error("API error message: %s, error code is %s"
                     % (e.message, e.get_error_code()))
        logger.error("fail to destroy domain")
        return 1

    newguestxml = redefine_vcpu_number(domobj, guestname, vcpu)
    logger.debug('''new guest %s xml :\n%s''' % (guestname, newguestxml))

    logger.info("undefine the original guest")
    try:
        domobj.undefine()
    except libvirtError as e:
        logger.error("API error message: %s, error code is %s"
                     % (e.message, e.get_error_code()))
        logger.error("fail to undefine guest %s" % guestname)
        return 1

    logger.info("define guest with new xml")
    try:
        conn = domobj._conn
        conn.defineXML(newguestxml)
    except libvirtError as e:
        logger.error("API error message: %s, error code is %s"
                     % (e.message, e.get_error_code()))
        logger.error("fail to define guest %s" % guestname)
        return 1

    try:
        logger.info('boot guest up ...')
        domobj.create()
    except libvirtError as e:
        logger.error("API error message: %s, error code is %s"
                     % (e.message, e.get_error_code()))
        logger.error("fail to start domain %s" % guestname)
        return 1

    timeout = 600

    while timeout:
        time.sleep(10)
        timeout -= 10

        logger.debug("get ip by mac address")
        ip = utils.mac_to_ip(mac, 180)
        logger.debug("the ip address of vm %s is %s" % (guestname, ip))

        if not ip:
            logger.info(str(timeout) + "s left")
        else:
            logger.info("vm %s power on successfully" % guestname)
            logger.info("the ip address of vm %s is %s" % (guestname, ip))
            break

    if timeout <= 0:
        logger.info("fail to power on vm %s" % guestname)
        return 1

    ret = check_current_vcpu(domobj, username, password)
    if ret != 'False':
        return 0
    else:
        return 1

    return 0


def cpu_hotplug(params):
    """set vcpu of virtual machine to value of parameter vcpu and
       current cpu as 1, then loop set runnning domain vcpu from
       min to max and loop hotplug it to min
    """
    global logger
    logger = params['logger']
    params.pop('logger')
    guestname = params['guestname']
    vcpu = int(params['vcpu'])
    username = params['username']
    password = params['password']

    logger.info("the name of virtual machine is %s" % guestname)
    logger.info("the vcpu given is %s" % vcpu)
    if not vcpu > 1:
        logger.error("vcpu number should bigger than 1")
        return 1

    conn = sharedmod.libvirtobj['conn']

    try:
        max_vcpus = int(conn.getMaxVcpus('kvm'))
        logger.debug("hypervisor supported max vcpu is %s" % max_vcpus)
    except libvirtError as e:
        logger.error("libvirt call failed: " + str(e))
        return 1

    if vcpu > max_vcpus:
        logger.error("the given vcpu %s is bigger than hypervisor supported" %
                     vcpu)
        return 1

    ret = check_domain_running(conn, guestname)
    if ret:
        return 1

    logger.debug("get the mac address of vm %s" % guestname)
    global mac
    mac = utils.get_dom_mac_addr(guestname)
    logger.debug("the mac address of vm %s is %s" % (guestname, mac))

    domobj = conn.lookupByName(guestname)

    logger.info("set domain vcpu to %s and restart with current cpu as 1" %
                vcpu)
    ret = set_vcpus(domobj, guestname, vcpu, username, password)
    if ret != 0:
        return 1

    try:
        max = domobj.maxVcpus()
        logger.info("max vcpu of domain %s is %s" % (guestname, max))
    except libvirtError as e:
        logger.error("libvirt call failed: " + str(e))
        return 1

    logger.info("loop increasing domain %s vcpu count to max" % guestname)
    for i in range(max):
        i += 1
        try:
            domobj.setVcpus(i)
            logger.info("set vcpus to %s" % i)
        except libvirtError as e:
            logger.error("libvirt call failed: " + str(e))
            return 1

        time.sleep(5)

        ret = check_current_vcpu(domobj, username, password)
        if ret == i:
            logger.info("current vcpu number is %s and equal to set" % ret)
        else:
            logger.error("set current vcpu failed")
            return 1

    logger.info("loop decreasing domain %s vcpu count to min" % guestname)
    for i in reversed(range(max)):
        if i == 0:
            break
        logger.info("set vcpus to %s" % i)
        try:
            max = domobj.setVcpus(i)
        except libvirtError as e:
            logger.error("libvirt call failed: " + str(e))
            return 1

        time.sleep(5)

        ret = check_current_vcpu(domobj, username, password)
        if ret == i:
            logger.info("current vcpu number is %s and equal to set" % ret)
        else:
            logger.error("set current vcpu failed")
            return 1

    return 0
