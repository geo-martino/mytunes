Load and save tags to a local track
===================================

In this example, you will:
   * Load a local track
   * Modify the tags of a local track and save them to the file


.. include:: setup.logging.txt


Load a track
------------

Load a track as follows:

.. literalinclude:: scripts/local.track.load-save/p1.py
   :language: Python

You can also just have MyTunes automatically determine the track type to load based on the file's extension:

.. literalinclude:: scripts/local.track.load-save/p1_load.py
   :language: Python
   :lines: 3-

If you want to be able to assign a URI to your track, you'll need to provide a :py:class:`.RemoteDataWrangler`
to the track object for the relevant music streaming source.

The following is an example for doing this with Spotify as the data source:

.. literalinclude:: scripts/local.track.load-save/p1_wrangler.py
   :language: Python
   :lines: 3-


Modify the track's tags and save them
-------------------------------------

1. Change some tags:

   .. literalinclude:: scripts/local.track.load-save/p2.py
      :language: Python
      :lines: 3-

2. Save all the modified tags to the file:

   .. literalinclude:: scripts/local.track.load-save/p3_all.py
      :language: Python
      :lines: 3-

   ... or select exactly which modified tags you wish to save:

   .. literalinclude:: scripts/local.track.load-save/p3_tags.py
      :language: Python
      :lines: 3-
