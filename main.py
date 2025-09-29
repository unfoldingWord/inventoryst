from dotenv import load_dotenv
from platforms import *
import logging
import traceback
import datetime
import psutil
import os
from pprint import pp

load_dotenv()


class Inventoryst:
    def __init__(self):
        self.__config = Platform.load_config('general')
        self.__logger = self.init_logger()
        self.__metrics = {'inventoryst': {}}

    def init_logger(self):
        this_logger = logging.getLogger()

        if not this_logger.hasHandlers():
            c_handler = logging.StreamHandler()
            if self.__config['stage'] == 'dev':
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

    def __add_metric(self, key, value):
        ts = datetime.datetime.now()
        self.__metrics['inventoryst'][key] = value

    def inventorize(self):
        lst_inventories_to_fetch = self.__config['inventories']

        # Process all requested platforms
        processed_platforms = 0
        page_change_count = 0
        api_calls = dict()
        for platform in lst_inventories_to_fetch:
            self.__logger.info(f'Processing {platform}...')
            duration_date_start = datetime.datetime.now()
            memory_usage_start = psutil.Process(os.getpid()).memory_info().rss

            try:
                obj_platform = eval(f"{platform}()")
                obj_platform.inventorize()
                processed_platforms += 1
                api_calls[platform] = obj_platform.get_api_calls()
                page_change_count += obj_platform.get_changed_page_count()

            except Exception as e:
                self.__logger.error(f"Processing of {platform} encountered an error")
                self.__logger.error(e)
                traceback.print_exc()

            # Time spent
            duration_date_end = datetime.datetime.now()
            duration = duration_date_end - duration_date_start

            # Memory usage
            memory_usage_end = psutil.Process(os.getpid()).memory_info().rss
            memory_usage = memory_usage_end - memory_usage_start

            p_metrics = {
                'duration': f'{duration.seconds}.{round(duration.microseconds, 2)}',
                'memory_usage': memory_usage
            }
            self.__add_metric(platform, p_metrics)

        self.__logger.debug(f'Api calls: {str(api_calls)}')
        self.__logger.info(f'Metrics: {str(self.__metrics)}')

        self.__logger.info(f"Platforms requested: {len(lst_inventories_to_fetch)} / "
                           f"Platforms processed: {processed_platforms} / "
                           f"Pages changed: {page_change_count}" )

obj_inventoryst = Inventoryst()
obj_inventoryst.inventorize()
