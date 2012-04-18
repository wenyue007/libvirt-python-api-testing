#!/usr/bin/env python

import os
import re
import sys

import libvirt
from libvirt import libvirtError

from src import sharedmod
from utils import xmlbuilder

required_params = ('poolname', 'pooltype',)
optional_params = ('targetpath',)

def display_pool_info(conn):
    """Display current storage pool information"""
    logger.debug("current define storage pool: %s" % \
                  conn.listDefinedStoragePools())
    logger.debug("current active storage pool: %s" % conn.listStoragePools())

def check_pool_define(poolname):
    """This function will check if the storage pool with
       the given poolname existed already.It first checks
       if the storagepool xml file exists in /etc/libvirt/storage
       directory
    """
    path = "/etc/libvirt/storage/%s.xml" % poolname
    logger.debug("%s xml file path: %s" % (poolname, path))

    if os.access(path, os.R_OK):
        return True
    else:
        return False

def define_mpath_pool(params):
    """Define a mpath type storage pool from xml"""

    global logger
    logger = params['logger']
    params.pop('logger')
    poolname = params['poolname']
    pooltype = params['pooltype']

    logger.info("the poolname is %s, pooltype is %s" % (poolname, pooltype))

    conn = sharedmod.libvirtobj['conn']

    if check_pool_define(poolname):
        logger.error("%s storage pool is defined" % poolname)
        return 1

    xmlobj = xmlbuilder.XmlBuilder()
    poolxml = xmlobj.build_pool(params)
    logger.debug("storage pool xml:\n%s" % poolxml)

    pool_num1 = conn.numOfDefinedStoragePools()
    logger.info("original storage pool define number: %s" % pool_num1)
    display_pool_info(conn)

    try:
        logger.info("define %s storage pool" % poolname)
        conn.storagePoolDefineXML(poolxml, 0)
        pool_num2 = conn.numOfDefinedStoragePools()
        logger.info("current storage pool define number: %s" % pool_num2)
        display_pool_info(conn)
        if check_pool_define(poolname) and pool_num2 > pool_num1:
            logger.info("It is successful to define %s storage pool" % poolname)
        else:
            logger.error("%s storage pool was not defined successfully" % \
                          poolname)
            return 1
    except libvirtError, e:
        logger.error("API error message: %s, error code is %s" \
                     % (e.message, e.get_error_code()))
        return 1

    return 0
