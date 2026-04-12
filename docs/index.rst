==================
Welcome to MyTunes!
==================

A Swiss Army knife for music library management
-----------------------------------------------

Helping you to manage your local and music streaming service (remote) libraries.

Features
--------

* Extract data for all item types from remote libraries, including following/saved items,
  such as: playlists, tracks, albums, artists, users, podcasts, audiobooks
* Load local audio files, programmatically manipulate, and save tags/metadata/embedded images
* Synchronise local tracks metadata with its matching track's metadata on supported music streaming services
* Synchronise local playlists with playlists on supported music streaming services
* Backup and restore track tags/metadata and playlists for local and remote libraries
* Extract and save images from remote tracks or embedded in local tracks

What's in this documentation
----------------------------

* How-to guides on getting started with MyTunes and other key functionality of the package
* Release history
* How to get started with contributing to MyTunes
* Reference documentation

.. include:: howto/install.rst
   :start-after: :

.. toctree::
   :maxdepth: 1
   :caption: 📜 How to...

   howto/install
   howto/local.library.load
   howto/local.playlist.load-save
   howto/local.track.load-save
   howto/spotify.load
   howto/library.backup-restore
   howto/sync
   howto/remote.new-music
   howto/reports

.. toctree::
   :maxdepth: 1
   :caption: 🛠️ Project Info

   info/release-history
   info/contributing
   info/licence

.. toctree::
   :maxdepth: 1
   :caption: 📖 Reference

   reference/mytunes.file
   reference/mytunes.libraries
   reference/mytunes.processors
   reference/mytunes.base
   reference/mytunes.exception
   reference/mytunes.field
   reference/mytunes.logger
   reference/mytunes.printer
   reference/mytunes.report
   reference/mytunes.types
   reference/mytunes.utils

.. raw:: html

   <hr>

.. toctree::
   :maxdepth: 1

   genindex
