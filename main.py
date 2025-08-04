from dotenv import load_dotenv
from platforms import *
import logging
import os
import traceback

load_dotenv()


class Inventoryst:
    def __init__(self):
        self.__logger = self.init_logger()

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
        lst_inventories_to_fetch = os.getenv('FETCH_INVENTORIES').split(',')

        map_inventories = {
            'readthedocs': 'ReadTheDocs', # ReadTheDocs
            'netlify': 'Netlify',         # Netlify
            'dns': 'DNS',                 # DNS (EPIK, Namecheap)
            'mysql': 'MySQL',             # MySQL
            'zoom': 'Zoom',               # Zoom
            'discourse': 'Discourse'      # Discourse
        }

        for platform in lst_inventories_to_fetch:
            self.__logger.info(f'Processing {map_inventories[platform]}...')

            try:
                obj_platform = eval(f"{map_inventories[platform]}()")
                obj_platform.inventorize()
            except Exception as e:
                self.__logger.error(f"Processing of {map_inventories[platform]} encountered an error")
                self.__logger.error(e)
                traceback.print_exc()


obj_inventoryst = Inventoryst()
obj_inventoryst.inventorize()
