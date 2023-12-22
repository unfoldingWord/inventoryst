from dotenv import load_dotenv
from platforms import *
import logging
import os

load_dotenv()


class Inventoryst:
    def __init__(self):
        self.init_logger()

    def init_logger(self):
        this_logger = logging.getLogger()

        if not this_logger.hasHandlers():
            c_handler = logging.StreamHandler()
            if os.getenv('STAGE', False) == 'dev':
                c_handler.setLevel(logging.DEBUG)
                this_logger.setLevel(logging.DEBUG)
            else:
                c_handler.setLevel(logging.INFO)
                this_logger.setLevel(logging.INFO)

            log_format = '%(asctime)s  %(levelname)-8s %(message)s'
            c_format = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
            c_handler.setFormatter(c_format)

            this_logger.addHandler(c_handler)

        return this_logger

    def inventorize(self):
        inventories_to_fetch = os.getenv('FETCH_INVENTORIES')

        # ReadTheDocs
        if 'readthedocs' in inventories_to_fetch:
            obj_rtd = ReadtheDocs()
            obj_rtd.inventorize()

        # Netlify
        if 'netlify' in inventories_to_fetch:
            obj_nlf = Netlify()
            obj_nlf.inventorize()

        # DNS (EPIK, Namecheap)
        if 'dns' in inventories_to_fetch:
            obj_dns = DNS()
            obj_dns.inventorize()

        # MySQL
        if 'mysql' in inventories_to_fetch:
            obj_mysql = MySQL()
            obj_mysql.inventorize()


obj_inventoryst = Inventoryst()
obj_inventoryst.inventorize()
