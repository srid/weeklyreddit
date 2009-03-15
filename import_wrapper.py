import os
import sys
import glob
import logging

# Add 3rdparty/*.zip to sys.path so that we can import them seamlessly
root = os.path.dirname(__file__)
for ziplib in glob.glob(os.path.join(root, '3rdparty', '*.zip')):
    logging.debug("Adding 3rdparty library '%s' to sys.path" % ziplib)
    sys.path.insert(0, ziplib)
