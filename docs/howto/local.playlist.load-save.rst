Create, load, and update a local playlist
=========================================

In this example, you will:
   * Create a local playlist from scratch
   * Load a local playlist
   * Modify the tracks in a playlist and save the changes to the file


.. include:: setup.logging.txt


Create a playlist
-----------------

You can create a playlist from scratch as follows:

.. literalinclude:: scripts/local.playlist.load-save/p1.py
   :language: Python

Load a playlist
---------------

You can load a playlist as per the blow code.

If you already have some tracks loaded, and you want the playlist to only use those tracks instead of loading
the tracks itself, you can pass these preloaded tracks to the playlist too. This will still load the playlist
from the given file, but it will use the given track objects instead of loading and creating new ones.

.. note::
   To be able to use the XAutoPF playlist type, you will need to have installed the ``musicbee`` optional dependencies.
   See :ref:`installation` for more details.

.. literalinclude:: scripts/local.playlist.load-save/p2.py
   :language: Python
   :lines: 3-

You can also just have MyTunes automatically determine the playlist type to load based on the file's extension:

.. literalinclude:: scripts/local.playlist.load-save/p3.py
   :language: Python
   :lines: 3-

There may also be cases where the files in the file need mapping to be loaded e.g. if the paths
contained in the playlist file are relative paths.
You may give the playlist object a :py:class:`.PathMapper` or :py:class:`.PathStemMapper` to handle this.

.. literalinclude:: scripts/local.playlist.load-save/p3_mapper.py
   :language: Python
   :lines: 3-

If you want to be able to read/update URIs on the loaded tracks,
you'll need to provide a :py:class:`.RemoteDataWrangler`
to the playlist object for the relevant music streaming source.

The following is an example for doing this with Spotify as the data source:

.. literalinclude:: scripts/local.playlist.load-save/p3_wrangler.py
   :language: Python
   :lines: 3-


Modify and save the playlist
----------------------------

1. Add some tracks to the playlist:

   .. literalinclude:: scripts/local.playlist.load-save/p4.py
      :language: Python
      :lines: 3-

2. Save the playlist:

   .. literalinclude:: scripts/local.playlist.load-save/p5.py
      :language: Python
      :lines: 3-
