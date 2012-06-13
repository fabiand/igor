
import os
import ConfigParser
import logging

logger = logging.getLogger(__name__)

search_paths = [".", "~/.igord", "/etc/igord"]

def flatten_config(cfg):
    cfgdict = {}
    for section in cfg.sections():
        for name, value in cfg.items(section):
            key = "%s.%s" % (section.lower(), name)
            cfgdict[key] = value
    return cfgdict

def parse_config(fn = "igord.cfg"):
    cfg = ConfigParser.SafeConfigParser()
    was_read = False
    for sp in search_paths:
        filename = os.path.join(sp, fn)
        if os.path.exists(filename):
            logger.info("Loading config from '%s'" % filename)
            cfg.read(filename)
            was_read = True
    assert was_read == True, "Config file not found"

    return flatten_config(cfg)
