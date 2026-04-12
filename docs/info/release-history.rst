.. Add log for your proposed changes here.

   The versions shall be listed in descending order with the latest release first.

   Change categories:
      Added          - for new features.
      Changed        - for changes in existing functionality.
      Deprecated     - for soon-to-be removed features.
      Removed        - for now removed features.
      Fixed          - for any bug fixes.
      Security       - in case of vulnerabilities.
      Documentation  - for changes that only affected documentation and no functionality.

   Your additions should keep the same structure as observed throughout the file i.e.

      <release version>
      =================

      <one of the above change categories>
      ------------------------------------
      * <your 1st change>
      * <your 2nd change>
      ...

.. _release-history:

===============
Release History
===============

The format is based on `Keep a Changelog <https://keepachangelog.com/en>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_


1.2.5
=====

Fixed
-----
* :py:meth:`.RemoteLibrary.log_tracks` now displays correct counts


1.2.5
=====

Fixed
-----
* :py:meth:`.RemoteLibrary.log_sync` now correctly gets max width from results
  when :py:class:`.RemotePlaylist` is given in results


1.2.4
=====

Fixed
-----
* :py:class:`.RemotePlaylist` is now hashable again


1.2.3
=====

Changed
-------
* Allow :py:class:`.RemotePlaylist` to be passed to :py:meth:`.RemoteLibrary.log_sync`


1.2.2
=====

Changed
-------
* :py:class:`.Track` implementations no longer match on name only. This avoids over matching that was noticed
  when running :py:meth:`.LocalCollection.merge_tracks`.


1.2.1
=====

Changed
-------
* May now define custom ignore words when sorting string values using the :py:class:`.ItemSorter`
* :py:class:`.ItemSorter` ignore case when sorting string values

Fixed
-----
* Paths are now sanitised when assigning ``filename`` to :py:class:`.LocalTrack`
* :py:class:`.Comparer` no longer needs an expected value set for methods which do not use it
* :py:class:`.Comparer` handles null values in expected values as needed


1.2.0
=====

Added
-----
* Can now get tags from any :py:class:`.MyTunesItem` and set tags on any :py:class:`.LocalTrack`
  using the relevant :py:class:`.Field` enums
* Equality comparison methods to all implementations of :py:class:`.Filter`
* :py:class:`.BasicLocalCollection` for creating and managing arbitrary local collections
* :py:class:`.MyTunesEnum` now displayed correctly when outputting to ``json`` on :py:class:`.PrettyPrinter` objects
* :py:meth:`.LocalTrack.move` and :py:meth:`.LocalTrack.rename` methods to handle moving the file on the disk.
* Set the ``path`` and ``filename`` properties on a :py:class:`.LocalTrack` to defer the movement of a file on the disk.
  Setting a new path in this way does not immediately move a file.
  Instead, the file will be moved when :py:meth:`.LocalTrack.save` is called with a ``path`` type
  tag field as an argument.

Changed
-------
* Track number zero fill amount is now calculated from the track total value
  when writing track tags on :py:class:`.LocalTrack`
* Simplified ``dict`` output from :py:class:`.FilterComparers`
* Field names displayed as lower case in ``dict`` output on relevant :py:class:`.PrettyPrinter` implementations
* Expand logging for results from saving tracks on local collections

Fixed
-----
* Drop ``null`` responses from Spotify API which cause bugs in execution logic
* Bug in :py:meth:`.LocalLibrary.load_tracks` that would cause it to store ``None`` when the track could not be loaded


1.1.10
======

Fixed
-----
* Bug in :py:class:`.Comparer` methods which caused them to fail on invalid expected values


1.1.9
=====

Changed
-------
* :py:class:`.Comparer` now correctly ignores the reference track given when the ``reference_required`` flag is False.

Fixed
-----
* Bug in :py:class:`.XAutoPF` which caused it to always add the tracks that matched the associated tags of
  the last played track when the expected values for the condition are null or empty.


1.1.8
=====

Fixed
-----
* Bug in :py:class:`.RemoteItemChecker` that tries to remove items from the `added` list when they are not present
  whilst trying to match items to remote playlist.

1.1.7
=====

Fixed
-----
* Handle bad values for bpm and compilation in :py:class:`.TagReader` by returning ``None``.

1.1.6
=====

Fixed
-----
* Remove '&' character handling in :py:class:`.XMLPlaylistParser`. Was being handled twice as it is already
  handled by the ``xmltodict`` package.


1.1.5
=====

Fixed
-----
* Bug in escaping of '&' characters when export :py:class:`.XAutoPF` playlists with the :py:class:`.XMLPlaylistParser`.
  Was previously escaping multiple times when already escaped e.g. '&amp;amp;' > '&amp;amp;amp;'.
  Now correctly skips already occurrences of '&'.


1.1.4
=====

Added
-----
* :py:class:`.LocalPlaylist` now allows setting of the ``path`` property
* :py:class:`.LocalLibrary` now allows setting of the ``name`` property. Added ``name`` as an init parameter too.

Changed
-------
* :py:meth:`.LocalLibrary.merge_playlists` now updates the path of new playlists added to the library to be relative
  to the library's ``playlist_folder``


1.1.3
=====

Fixed
-----
* When given an empty :py:class:`.M3U` playlist file, produces expected result i.e. an empty playlist.
  Previously always added all given tracks to playlist when calling :py:meth:`.M3U.load`


1.1.2
=====

Changed
-------
* :py:meth:`.File.get_filepaths` now ignores hidden files.
* Replace os.makedirs with Pathlib implementation of ``mkdir`` everywhere.


1.1.1
=====

Changed
-------
* Update aiorequestful version to 1.0


1.1.0
=====

Changed
-------
* :py:class:`.ItemDownloadHelper` only ever takes the first field when the singular name of a field is given
  and many values are available for that field. e.g. only ever takes the first artist when multiple artists are present
  and the requested field is 'artist' and not 'artists'
* :py:class:`.RemoteCollectionLoader` now inherits from :py:class:`.MyTunesItem` interface.
  The class already implemented all necessary methods for this interface and was always designed
  to be an implementation of the :py:class:`.MyTunesItem` interface.
* Rename ``print`` method on :py:class:`.MyTunesLogger` to :py:meth:`.MyTunesLogger.print_line`

Removed
-------
* Implementation of REST API handling including all cache + authorisation implementations.
  Separated this off to a `new package <https://github.com/geo-martino/aiorequestful>`_.
* Moved all enum definitions to ``types`` modules and removed all ``enum`` modules.

Documentation
-------------
* Fix references to non-existent packages + add missing packages in API reference index


1.0.2
=====

Added
-----
* Expanded error message on :py:class:`.DynamicProcessor` processor lookup exception.
* Improved logging of bad responses on :py:class:`.RequestHandler`
* ``wait_max`` time to cap wait time between requests for :py:class:`.RequestHandler`
* Add log on :py:class:`.CachedSession` for when either a `cache hit` or a `HTTP request` happens.

Removed
-------
* ``limiter_deduplication`` attribute from print output on :py:class:`.XAutoPF`

Fixed
-----
* Bug in :py:class:`.XMLLibraryParser` which would not read 'Playlists' keys.
* Moved 'check api' logic later when deleting playlists in :py:class:`.RemoteItemChecker`
  to ensure API is not checked on close when checker has not actually run.
* :py:class:`.RequestHandler` now handles wait and backoff logic asynchronously.
* Tracks on playlists from the JSON output of :py:class:`.LocalLibrary` now display correctly.
  Previously showed 'null' for every track.


1.0.1
=====

Documentation
-------------
* Mark release as stable/production.


1.0.0
=====

Added
-----

* Custom API caching backend to replace dependency on ``requests-cache`` package.
  Currently only supports SQLite backend. More backends can be implemented in future if desired.
* Cache settings for specific `GET` request endpoints on :py:class:`.SpotifyAPI` replacing need
  for per method ``use_cache`` parameter.
* The following classes should now be run as AsyncContextManagers to function correctly:
   * :py:class:`.SQLiteCache`
   * :py:class:`.RequestHandler`
   * :py:class:`.CachedSession`
   * :py:class:`.RemoteAPI` & :py:class:`.SpotifyAPI`
* Introduce print wrapper for logger and remove most bare ``print`` statements across package.
* :py:meth:`.SpotifyAPI.extend_items` now enriches collection item responses with the parent collection response.
* ARTISTS field added to LocalTrackField
* Add compatibility with ``yarl`` package for any logic which uses URL logic.
* Add compatibility for pathlib.Path for any logic which uses path logic.
* Extended logging on :py:func:`.report_playlist_differences`
* ``source`` property on :py:class:`.Library`
* :py:meth:`.RemoteAPI.get_or_create_playlist` method for only creating a playlist when it doesn't
  already exist by name. Gets the existing playlist otherwise
* Added :py:meth:`.MyTunesCollection.outer_difference` method to cover the logic previously handled
  by the mislabelled :py:meth:`.MyTunesCollection.outer_difference` method
* :py:class:`.RemoteDataWrangler` and its implementations now handle URL objects from the ``yarl`` package
* :py:meth:`.RemoteAPI.follow_playlist` method
* Wait time logic for :py:class:`.RequestHandler`. This waits by a certain time after each request,
  incrementing this wait time every time a 429 code is returned.
  This allows better handling of rate limits, with the aim of preventing a lock out from a service.

Changed
-------

* :py:class:`.RequestHandler` now handles requests asynchronously. These changes to async calls have
  been implemented all the way on :py:class:`.RemoteAPI` and all other objects that depend on it.
* All I/O operations on local libraries and their dependent objects now run asynchronously.
* Dependency injection pattern for :py:class:`.RequestHandler`.
  Now takes :py:class:`.APIAuthoriser` and generator for :py:class:`.ClientSession` objects for instantiation
  instead of kwargs for :py:class:`.APIAuthoriser`.
* Dependency injection pattern for :py:class:`.RemoteAPI`.
  Now takes :py:class:`.APIAuthoriser` and generator for :py:class:`.ResponseCache` objects for instantiation
  instead of kwargs for :py:class:`.APIAuthoriser`.
* :py:class:`.APIAuthoriser` kwargs given to :py:class:`.SpotifyAPI` now merge with default kwargs.
* Moved ``remote_wrangler`` attribute from :py:class:`.MyTunesCollection` to :py:class:`.LocalCollection`.
  This attribute was only needed by :py:class:`.LocalCollection` branch of child classes.
* Moved ``logger`` attribute from :py:class:`.Library` to :py:class:`.RemoteLibrary`.
* Switch some dependencies to be optional for groups of operation: progress bars, musicbee, sqlite
* Replace urllib usages with ``yarl`` package.
* Replace all path logic to use pathlib.Path instead. All
* :py:class:`.SpotifyAPI` now logs to the new central :py:meth:`.RequestHandler.log` method
  to help unify log formatting.
* ``user_id`` and ``user_name`` now raise an error when called before setting ``user_data`` attribute.
  This is due to avoiding asynchronous calls in a property.
  It is therefore best to now enter the async context of the api to set these automatically.
* Renamed :py:meth:`.LocalGenres.genres` to :py:meth:`.LocalGenres.related_genres`
* Reduced scope of :py:meth:`.TagWriter._delete_tag` method to private
* :py:class:`.LocalTrack` now removes any loaded embedded image from the mutagen file object.
  This is to reduce memory usage when loading many of these objects.
* Extend logging on :py:meth:`.LocalCollection.log_save_tracks_result` to show when no tags
  have been or would be updated.
* :py:class:`.RemoteItemChecker` now uses the new :py:meth:`.RemoteAPI.get_or_create_playlist` method
  when creating playlists to avoid creating many duplicate playlists which could have lead to playlist
  creation explosion in repeated uses. The processor also accounts for any items that may have existed
  in the playlist before it was run and discounts them from any matches.
* :py:class:`.RemoteItemChecker` also uses the new :py:meth:`.RemoteAPI.follow_playlist` method
  when creating playlists to ensure that a user is following the playlists it creates to avoid 'ghost playlist' issue.
* :py:meth:`.SpotifyAPI.create_playlist` now returns the full response rather than just the URL of the playlist.
* Moved :py:class:`.RemoteItemChecker` and :py:class:`.RemoteItemSearcher` to `mytunes.processors` package.
* Moved :py:class:`.RemoteDataWrangler` up a level to `mytunes.libraries.remote.core`.
* Renamed `mytunes.libraries.remote.spotify.processors` module to `mytunes.libraries.remote.spotify.wrangle`.
* Moved `mytunes.logger` module to `mytunes` base package.
* Restructured contents of `mytunes.core` package to modules in `mytunes` base package.

Fixed
-----

* Added missing variables to __slots__ definitions
* Correctly applied __slots__ pattern to child classes. Now works as expected.
* :py:class:`.LocalTrack` now copies tags as expected when calling ``copy.copy()``
* Bug where loading an M3U playlist with new track objects would force all created track objects
  to have lower case paths
* :py:meth:`.RemoteLibrary.restore_playlists` now correctly handles the backup
  output from :py:meth:`.RemoteLibrary.backup_playlists`
* Issue detecting stdout_handlers affecting :py:meth:`.MyTunesLogger.print` and :py:meth:`.MyTunesLogger.get_iterator`.
  Now works as expected.
* :py:meth:`.LocalLibrary.artists` now generates a :py:class:`.LocalArtist` object per individual artist
  rather than on combined artists
* Issue where :py:meth:`.SpotifyAPI.extend_items` did not show progress when extending some types of responses
* Fixed logic in :py:meth:`.MyTunesCollection.intersection` and :py:meth:`.MyTunesCollection.difference`

Removed
-------

* Dependency on ``requests`` package in favour of ``aiohttp`` for async requests.
* Dependency on ``requests-cache`` package in favour of custom cache implementation.
* ``use_cache`` parameter from all :py:class:`.RemoteAPI` related methods.
  Cache settings now handled by :py:class:`.ResponseCache`
* ThreadPoolExecutor use on :py:class:`.RemoteItemSearcher`. Now uses asynchronous logic instead.
* `last_modified` field as attribute to ignore when getting attributes
  to print on `LocalCollection` to improve performance
* Removed logger filters and handlers. Moved to CLI repo.
* Deleted `mytunes.libraries.remote.core.processors` package.

Documentation
-------------

* Updated how-to section to reflect implementation of async logic to underlying code
* Created a how-to page for installation


0.9.2
=====

Added
-----

* ``REMOTE_SOURCES`` global variable in the ``libraries.remote`` module which lists the
  names of all the fully supported remote sources.
  Also, added the ``SOURCE_NAME`` global variable for the Spotify module.

Changed
-------

* :py:class:`.FilterComparers` now accepts a single :py:class:`.Comparer` on the ``comparers`` argument.
* :py:class:`.MusicBee` class attributes were renamed to classify that full paths are also valid, not just filenames.
* :py:class:`.ItemDownloadHelper` ``urls`` init arg now has default arg of empty tuple.

Documentation
-------------

* Fixed error in 'sync data' how-to.

Fixed
-----

* :py:class:`.Comparer` now considers strings as converted on first pass when converting expected values.
* Printing of new line at the end of :py:meth:`.RemoteLibrary.extend`

0.9.1
=====

Fixed
-----

* Bug in :py:meth:`.ItemMatcher.match` where operations always returned the last item in the given list of ``results``


0.9.0
=====

Added
-----

* :py:class:`.RemoteAPI` methods now accept :py:class:`.RemoteResponse` objects as input, refreshing them automatically
* Property 'kind' to all objects which have an associated :py:class:`.RemoteObjectType`
* Introduced :py:class:`.MyTunesItemSettable` class to allow distinction
  between items that can have their properties set and those that can't
* Extend :py:class:`.FilterMatcher` with group_by tag functionality
* Now fully supports parsing of processors relating to :py:class:`.XAutoPF` objects with full I/O of settings
  to/from their related XML files on disk
* Now supports creating new :py:class:`.XAutoPF` files from scratch without the file needing to already exist
  For XML values not directly controlled by MyTunes, users can use the 'default_xml' class attribute
  to control the initial default values applied in this scenario
* 'length' property on :py:class:`.MyTunesCollection` and implementation on all subclasses

Changed
-------

* Major refactoring and restructuring to all modules to improve modularity and add composition
* The following classes and methods have been modified to implement concurrency to improve performance:
   * :py:meth:`.LocalLibrary.load_tracks`
   * :py:meth:`.LocalLibrary.save_tracks`
   * :py:meth:`.LocalLibrary.load_playlists`
   * :py:meth:`.LocalLibrary.save_playlists`
   * :py:meth:`.LocalLibrary.json` + optimisation for extracting JSON data from tracks
   * :py:class:`.ItemMatcher`
   * :py:class:`.RemoteItemChecker`
   * :py:class:`.RemoteItemSearcher`
* Made :py:func:`.load_tracks` and :py:func:`.load_playlists` utility functions more DRY
* Move :py:meth:`.TagReader.load` from :py:class:`.LocalTrack` to super class :py:class:`.TagReader`
* :py:meth:`.SpotifyAPI.extend_items` now skips on responses that are already fully extended
* :py:meth:`.SpotifyArtist.load` now uses the base `load` method from :py:class:`.SpotifyCollectionLoader`
  meaning it now takes full advantage of the item filtering this method offers.
  As part of this, the base method was made more generic to accommodate all :py:class:`.SpotifyObject` types
* Renamed 'kind' property on :py:class:`.LocalTrack` to 'type' to avoid clashing property names
* :py:class:`.ItemMatcher`, :py:class:`.RemoteItemChecker`, and :py:class:`.RemoteItemSearcher` now accept
  all MyTunesItem types that may have their URI property set manually
* :py:class:`.RemoteItemChecker` and :py:class:`.RemoteItemSearcher` no longer inherit from :py:class:`.ItemMatcher`.
  Composite pattern used instead.
* :py:class:`.ItemSorter` now shuffles randomly on unsupported types
  + prioritises fields settings over shuffle settings
* :py:meth:`.Comparer._in_range` now uses inclusive range i.e. ``a <= x <= b`` where ``x`` is the value to compare
  and ``a`` and ``b`` are the limits. Previously used exclusive range i.e. ``a < x < b``
* Removed ``from_xml`` and ``to_xml`` methods from all :py:class:`.MusicBeeProcessor` subclasses.
  Moved this logic to :py:class:`.XMLPlaylistParser` as distinct 'get' methods for each processor type
* Moved loading of XML file logic from :py:class:`.XAutoPF` to :py:class:`.XMLPlaylistParser`.
  :py:class:`.XMLPlaylistParser` is now solely responsible for all XML parsing and handling
  for :py:class:`.XAutoPF` files

Fixed
-----

* :py:class:`.Comparer` dynamic processor methods which process string values now cast expected types before processing

Removed
-------

* Redundant ShuffleBy enum and related arguments from :py:class:`.ItemSorter`
* ``ItemProcessor`` and ``MusicBeeProcessor`` abstraction layers. No longer needed after some refactoring
* ``get_filtered_playlists`` method from :py:class:`.Library`.
  This contained author specific logic and was not appropriate for general use

Documentation
-------------

* Added info on lint checking for the contributing page

0.8.1
=====

Changed
-------

* :py:class:`.ItemSorter` now accepts ``shuffle_weight`` between -1 and 1 instead of 0 and 1.
  This parameter's logic has not yet been implemented so no changes to functionality have been made yet
* Move :py:meth:`.get_filepaths` from :py:class:`.LocalTrack` to super class :py:class:`.File`

Documentation
-------------

* References to python objects now link correctly

Fixed
-----

* Comments from :py:class:`.LocalTrack` metadata loading no longer gets wiped after setting URI on init
* Tweaked assignment of description of IDv3 comment tags for :py:class:`.MP3`
* :py:func:`.align_string` function now handles combining unicode characters properly for fixed-width fonts
* :py:meth:`.LocalTrack.get_filepaths` on LocalTrack no longer returns paths from ``$RECYCLE.BIN`` folders.
  These are deleted files and were causing the package to crash when trying to load them
* :py:meth:`.PrettyPrinter.json` and :py:meth:`.PrettyPrinter._to_str` converts attribute keys to string
  to ensure safe json/str/repr output
* :py:class:`.FilterMatcher` and :py:class:`.FilterComparers` now correctly import conditions from XML playlist files.
  Previously, these filters could not import nested match conditions from files.
  Changes to logic also made to :py:meth:`.Comparer.from_xml` to accommodate
* :py:class:`.XMLLibraryParser` now handles empty arrays correctly. Previously would crash
* Fixed :py:class:`.Comparer` dynamic process method alternate names for ``in_the_last`` and ``not_in_the_last``

Removed
-------

* Abstract uri.setter method on :py:class:`.Item`


0.8.0
=====

Added
-----

* Add debug log for error failure reason when loading tracks
* :py:meth:`.MyTunesCollection.intersection` and :py:meth:`.MyTunesCollection.difference` methods
* :py:meth:`.Playlist.merge` and :py:meth:`.Library.merge_playlists` methods

Changed
-------

* Generating folders for a :py:class:`.LocalLibrary` now uses folder names
  as relative to the library folders of the :py:class:`.LocalLibrary`.
  This now supports nested folder structures better
* Writing date tags to :py:class:`.LocalTrack` now supports partial dates of only YYYY-MM
* Writing date tags to :py:class:`.LocalTrack` skips writing year, month, day tags if date tag already written

Removed
-------

* set_compilation_tags method removed from :py:class:`.LocalFolder`.
  This contained author specific logic and was not appropriate for general use

Fixed
-----

* ConnectionError catch in :py:class:`.RequestHandler` now handles correctly
* Added safe characters and replacements for path conversion in MusicBee :py:class:`.XMLLibraryParser`.
  Now converts path to expected XML format correctly
* :py:class:`.FilterMatcher` now handles '&' character correctly
* :py:class:`.SpotifyAPI` now only requests batches of up to 20 items when getting albums.
  Now matches Spotify Web API specifications better
* Loading of logging yaml config uses UTF-8 encoding now
* Removed dependency on pytest-lazy-fixture.
  Package is `broken for pytest >8.0 <https://github.com/TvoroG/pytest-lazy-fixture/issues/65>`_.
  Replaced functionality with forked version of code


0.7.6
=====

Fixed
-----

* Rename __max_str in local/collection.py to _max_str - functions could not see variable
* Add default value of 0 to sort_key in :py:meth:`.ItemSorter.sort_by_field`
* Fixed :py:class:`.RemoteItemChecker` :py:meth:`._pause` logic to only get playlist name when input is not False-y


0.7.5
=====

Added
-----

* Add the :py:class:`.ItemDownloadHelper` general processor

Changed
-------

* Factor out logging handlers to their own script to avoid circular import issues
* Abstract away input methods of :py:class:`.RemoteItemChecker` to :py:class:`.InputProcessor` base class
* Factor out patch_input method to function in :py:class:`.InputProcessor` derived tests

Fixed
-----

* Captured stdout assertions in :py:class:`.RemoteItemChecker` tests re-enabled, now fixed
* Surround :py:class:`.RemoteAPI` 'user' properties in try-except block so they can still be
  pretty printed even if API is not authorised

Documentation
-------------

* Fix redirect/broken links
* Change notes text to proper rst syntax


0.7.4
=====

Fixed
-----

* Fix bug in :py:meth:`.LocalLibrary.restore_tracks` method on library
  due to 'images' tag name not being present in track properties

Documentation
-------------

* Expand docstrings across entire package
* Expand documentation with how to section, release history, and contributions pages


0.7.3
=====

Changed
-------

* Remove x10 factor on bar threshold on _get_items_multi function in :py:class:`.SpotifyAPI`

Fixed
-----

* :py:class:`.LocalTrack` would break when trying to save tags for unmapped tag names, now handles correctly


0.7.2
=====

Fixed
-----

* :py:class:`.MyTunesLogger` would not get file_paths for parent loggers when propagate == True, now it does


0.7.1
=====

Changed
-------

* Remove automatic assignment of absolute path to package root
  for relative paths on :py:class:`.CurrentTimeRotatingFileHandler`

Fixed
-----

* :py:class:`.CurrentTimeRotatingFileHandler` now creates dirs for new log directories


0.7.0
=====

Initial release! 🎉
