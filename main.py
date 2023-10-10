from dotenv import load_dotenv
from platform import *

load_dotenv()


class Inventoryst:
    def __init__(self):
        pass

    def inventorize(self):

        # ReadTheDocs
        obj_rtd = ReadtheDocs()
        obj_rtd.inventorize()


obj_inventoryst = Inventoryst()
obj_inventoryst.inventorize()
