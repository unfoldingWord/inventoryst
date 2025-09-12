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
            'discourse': 'Discourse',     # Discourse
            'notion': 'Notion',           # Notion
            'dockerhub': 'DockerHub',     # Docker Hub
            'github': 'Github'            # Github
        }

        # Process all requested platforms
        processed_platforms = 0
        page_change_count = 0
        api_calls = dict()
        for platform in lst_inventories_to_fetch:
            self.__logger.info(f'Processing {map_inventories[platform]}...')

            try:
                obj_platform = eval(f"{map_inventories[platform]}()")
                obj_platform.inventorize()
                processed_platforms += 1
                api_calls[platform] = obj_platform.get_api_calls()
                page_change_count += obj_platform.get_changed_page_count()

            except Exception as e:
                self.__logger.error(f"Processing of {map_inventories[platform]} encountered an error")
                self.__logger.error(e)
                traceback.print_exc()

        self.__logger.debug(f'Api calls: {str(api_calls)}')

        self.__logger.info(f"Platforms requested: {len(lst_inventories_to_fetch)} / "
                           f"Platforms processed: {processed_platforms} / "
                           f"Pages changed: {page_change_count}" )

obj_inventoryst = Inventoryst()
obj_inventoryst.inventorize()
