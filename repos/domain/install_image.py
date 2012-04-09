#!/usr/bin/env python

import os
import sys
import re
import time
import copy
import urllib

import libvirt
from libvirt import libvirtError

from utils import utils
from utils import env_parser
from utils import xmlbuilder

HOME_PATH = os.getcwd()

required_params = ('guestname', 'guesttype', 'guestos', 'guestarch')
optional_params = ('uuid',
                   'memory',
                   'vcpu',
                   'imagepath',
                   'imagetype',
                   'hdmodel',
                   'nicmodel')

def return_close(conn, logger, ret):
    conn.close()
    logger.info("closed hypervisor connection")
    return ret

def check_params(params):
    """Checking the arguments required"""
    params_given = copy.deepcopy(params)
    mandatory_args = ['guestname', 'guesttype', 'guestos', 'guestarch']
    optional_args = ['uuid', 'memory', 'vcpu', 'imagepath', 'imagetype',
                     'hdmodel', 'nicmodel']

    for arg in mandatory_args:
        if arg not in params_given.keys():
            logger.error("Argument %s is required." % arg)
            return 1
        elif not params_given[arg]:
            logger.error("value of argument %s is empty." % arg)
            return 1

        params_given.pop(arg)

    if len(params_given) == 0:
        return 0

    for arg in params_given.keys():
        if arg not in optional_args:
            logger.error("Argument %s could not be recognized." % arg)
            return 1

    return 0

def install_image(params):
    """ install a new virtual machine """
    # Initiate and check parameters
    global logger
    logger = params['logger']
    params.pop('logger')
    uri = params['uri']
    params.pop('uri')

    logger.info("Checking the validation of arguments provided.")
    params_check_result = check_params(params)

    if params_check_result:
        return 1

    logger.info("Arguments checkup finished.")

    guestname = params.get('guestname')
    guesttype = params.get('guesttype')
    guestos = params.get('guestos')
    guestarch = params.get('guestarch')

    logger.info("the name of guest is %s" % guestname)
    logger.info("the type of guest is %s" % guesttype)
    logger.info("the os of guest is %s" % guestos)
    logger.info("the arch of guest is %s" % guestarch)

    # Connect to local hypervisor connection URI
    hypervisor = utils.get_hypervisor()

    logger.info("the type of hypervisor is %s" % hypervisor)
    logger.debug("the uri to connect is %s" % uri)

    if params.has_key('imagepath'):
        imgfullpath = os.join.path(params.get('imagepath'), guestname)
    else:
        if hypervisor == 'xen':
            imgfullpath = os.path.join('/var/lib/xen/images', guestname)
        elif hypervisor == 'kvm':
            imgfullpath = os.path.join('/var/lib/libvirt/images',
                                       guestname)

    logger.info("the path of directory of disk images located on is %s" %
                 imgfullpath)

    envfile = os.path.join(HOME_PATH, 'env.cfg')
    logger.info("the environment file is %s" % envfile)

    envparser = env_parser.Envparser(envfile)
    image_url = envparser.get_value("image", "%s_%s" % (guestos, guestarch))

    logger.info("download images file from %s" % image_url)
    urllib.urlretrieve(image_url, imgfullpath)
    logger.info("the image is located in %s" % imgfullpath)

    conn = libvirt.open(uri)

    xmlobj = xmlbuilder.XmlBuilder()
    domain = xmlobj.add_domain(params)

    xmlobj.add_disk(params, domain)
    xmlobj.add_interface(params, domain)
    guestxml = xmlobj.build_domain(domain)

    try:
        domobj = conn.defineXML(guestxml)
    except libvirtError, e:
        logger.error("API error message: %s, error code is %s" \
                     % (e.message, e.get_error_code()))
        logger.error("fail to define domain %s" % guestname)
        return return_close(conn, logger, 1)

    logger.info("define guest %s " % guestname)
    logger.debug("the xml description of guest booting off harddisk is %s" %
                  guestxml)

    logger.info('boot guest up ...')

    try:
        domobj.create()
    except libvirtError, e:
        logger.error("API error message: %s, error code is %s" \
                     % (e.message, e.get_error_code()))
        logger.error("fail to start domain %s" % guestname)
        return return_close(conn, logger, 1)


    logger.info("get the mac address of vm %s" % guestname)
    mac = utils.get_dom_mac_addr(guestname)
    logger.info("the mac address of vm %s is %s" % (guestname, mac))

    timeout = 600

    while timeout:
        time.sleep(10)
        timeout -= 10

        ip = utils.mac_to_ip(mac, 180)

        if not ip:
            logger.info(str(timeout) + "s left")
        else:
            logger.info("vm %s power on successfully" % guestname)
            logger.info("the ip address of vm %s is %s" % (guestname, ip))
            break

        if timeout == 0:
            logger.info("fail to power on vm %s" % guestname)
            return return_close(conn, logger, 1)

    return return_close(conn, logger, 0)
