#!/usr/bin/env python
# Detach a disk from domain

import os
import re
import sys
import time

import libvirt
from libvirt import libvirtError

from src import sharedmod
from utils import utils

required_params = ('guestname',
                   'imageformat',
                   'hddriver',)
optional_params = {'diskpath': '/var/lib/libvirt/images/attacheddisk',
                   'xml': 'xmls/disk.xml',
                   }


def check_detach_disk(num1, num2):
    """Check detach disk result via simple disk number
       comparison
    """
    if num2 < num1:
        return True
    else:
        return False


def detach_disk(params):
    """Detach a disk to domain from xml"""
    logger = params['logger']
    guestname = params['guestname']
    imageformat = params['imageformat']
    hddriver = params['hddriver']
    xmlstr = params['xml']

    conn = sharedmod.libvirtobj['conn']
    domobj = conn.lookupByName(guestname)

    if hddriver == 'virtio':
        xmlstr = xmlstr.replace('DEV', 'vdb')
    elif hddriver == 'ide':
        xmlstr = xmlstr.replace('DEV', 'hdb')
    elif hddriver == 'scsi':
        xmlstr = xmlstr.replace('DEV', 'sdb')

    logger.debug("disk xml:\n%s" % xmlstr)

    disk_num1 = utils.dev_num(guestname, "disk")
    logger.debug("original disk number: %s" % disk_num1)

    try:
        domobj.detachDevice(xmlstr)
        disk_num2 = utils.dev_num(guestname, "disk")
        logger.debug("update disk number to %s" % disk_num2)
        if check_detach_disk(disk_num1, disk_num2):
            logger.info("current disk number: %s\n" % disk_num2)
        else:
            logger.error("fail to detach a disk to guest: %s\n" % disk_num2)
            return 1
    except libvirtError as e:
        logger.error("API error message: %s, error code is %s"
                     % (e.message, e.get_error_code()))
        logger.error("detach disk from guest %s" % guestname)
        return 1

    return 0
