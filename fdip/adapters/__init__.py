"""Adapters: the only layer that touches a database, a vendor SDK or the disk.

The domain layer imports none of this, and the import-graph test proves it.
"""
