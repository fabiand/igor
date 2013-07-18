#!/usr/bin/python
# To publish events via a redis instance
# The hookname and cookie are translated into XML
#

import sys
import igor.common as common
import redis


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise RuntimeError("Hookname or cookie missing: %s" % sys.argv)

    hookname, cookie = sys.argv[1:3]

    r = redis.Redis()
    r.publish(common.REDIS_EVENTS_PUBSUB_CHANNEL_NAME,
              "<event type='%s' session='%s' />" % (hookname, cookie))
