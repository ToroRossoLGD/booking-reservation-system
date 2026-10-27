"""Suppress credential-bearing occupancy URLs from Uvicorn access logs."""

import logging


class OccupancyAccessFilter(logging.Filter):
    def filter(self, record):
        return "/occupancy-feeds/" not in record.getMessage()


def install_feed_log_filter():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, OccupancyAccessFilter) for item in logger.filters):
        logger.addFilter(OccupancyAccessFilter())
